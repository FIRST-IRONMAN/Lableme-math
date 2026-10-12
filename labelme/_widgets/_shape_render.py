from __future__ import annotations

import dataclasses
import typing
from typing import Final
from typing import Literal

import numpy as np
import numpy.typing as npt
import skimage.measure
from PySide6 import QtCore
from PySide6 import QtGui

from .. import _utils
from .._shape import Shape
from .._shape import get_rotation_handle
from .._shape import nearest_edge_index
from .._shape import oriented_rectangle_arrow_points
from loguru import logger

PEN_WIDTH: Final[int] = 2


@dataclasses.dataclass(frozen=True)
class VertexHighlight:
    index: int
    mode: Literal["move", "near"]

    @property
    def size_factor(self) -> float:
        return {
            "move": 1.5,
            "near": 4.0,
        }[self.mode]

    @property
    def point_type(self) -> Literal["square", "round"]:
        match self.mode:
            case "move":
                return "square"
            case "near":
                return "round"
            case _:
                typing.assert_never(self.mode)


@dataclasses.dataclass(frozen=True)
class Palette:
    line: QtGui.QColor
    fill: QtGui.QColor
    select_line: QtGui.QColor
    select_fill: QtGui.QColor
    vertex_fill: QtGui.QColor
    hvertex_fill: QtGui.QColor

    @classmethod
    def from_rgb(cls, rgb: tuple[int, int, int]) -> Palette:
        r, g, b = rgb
        return cls(
            line=QtGui.QColor(r, g, b),
            fill=QtGui.QColor(r, g, b, 128),
            select_line=QtGui.QColor(255, 255, 255),
            select_fill=QtGui.QColor(r, g, b, 155),
            vertex_fill=QtGui.QColor(r, g, b),
            hvertex_fill=QtGui.QColor(255, 255, 255),
        )


@dataclasses.dataclass(frozen=True)
class ShapeRenderContext:
    scale: float
    palette: Palette
    point_size: int
    point_type: Literal["square", "round"]
    selected: bool
    fill: bool
    highlight: VertexHighlight | None
    rotation_highlight: VertexHighlight | None
    show_label: bool = False
    show_description: bool = False


def render_shape(
    painter: QtGui.QPainter, shape: Shape, context: ShapeRenderContext
) -> None:
    if shape.mask is None and len(shape.points) == 0:
        return

    palette = context.palette
    color = palette.select_line if context.selected else palette.line
    pen = QtGui.QPen(color)
    pen.setWidth(PEN_WIDTH)
    painter.setPen(pen)

    if shape.shape_type == "mask" and shape.mask is not None:
        _paint_shape_mask(painter=painter, shape=shape, context=context)

    if len(shape.points) > 0:
        _paint_shape_points(painter=painter, shape=shape, context=context)

    if context.show_label:
        _paint_shape_label(painter=painter, shape=shape, context=context)

    if context.show_description and shape.description:
        _paint_shape_description(painter=painter, shape=shape, context=context)


def _paint_shape_label(
    *,
    painter: QtGui.QPainter,
    shape: Shape,
    context: ShapeRenderContext,
) -> None:
    if not shape.label or len(shape.points) == 0:
        return
    # Anchor at the points' top-left so the text stays close to the shape and
    # tracks zoom/pan; lift it by the pen width to clear the outline stroke.
    top_left = shape.points.min(axis=0) * context.scale
    painter.setPen(QtGui.QPen(context.palette.line))
    painter.drawText(
        QtCore.QPointF(float(top_left[0]), float(top_left[1]) - PEN_WIDTH),
        shape.label,
    )


def _paint_shape_mask(
    *,
    painter: QtGui.QPainter,
    shape: Shape,
    context: ShapeRenderContext,
) -> None:
    assert shape.mask is not None
    fill = context.palette.select_fill if context.selected else context.palette.fill
    image_to_draw = np.zeros(shape.mask.shape + (4,), dtype=np.uint8)
    image_to_draw[shape.mask] = fill.getRgb()
    qimage = QtGui.QImage.fromData(_utils.img_arr_to_data(image_to_draw))
    origin = shape.points[0]
    target_top_left = origin * context.scale
    target_rect = QtCore.QRectF(
        target_top_left[0],
        target_top_left[1],
        qimage.width() * context.scale,
        qimage.height() * context.scale,
    )
    painter.drawImage(target_rect, qimage)

    path = QtGui.QPainterPath()
    contours = skimage.measure.find_contours(np.pad(shape.mask, pad_width=1))
    for contour in contours:
        contour = contour + [origin[1], origin[0]]
        path.moveTo(QtCore.QPointF(contour[0, 1], contour[0, 0]) * context.scale)
        for point in contour[1:]:
            path.lineTo(QtCore.QPointF(point[1], point[0]) * context.scale)
    painter.drawPath(path)


@dataclasses.dataclass(frozen=True)
class _ShapePaths:
    line: QtGui.QPainterPath = dataclasses.field(default_factory=QtGui.QPainterPath)
    vertices: QtGui.QPainterPath = dataclasses.field(default_factory=QtGui.QPainterPath)
    negative_vertices: QtGui.QPainterPath = dataclasses.field(
        default_factory=QtGui.QPainterPath
    )
    rotation_vertices: QtGui.QPainterPath = dataclasses.field(
        default_factory=QtGui.QPainterPath
    )
    orientation_arrow: QtGui.QPainterPath = dataclasses.field(
        default_factory=QtGui.QPainterPath
    )


def _paint_shape_points(
    *,
    painter: QtGui.QPainter,
    shape: Shape,
    context: ShapeRenderContext,
) -> None:
    palette = context.palette
    paths = _build_shape_points_paths(shape=shape, context=context)

    painter.drawPath(paths.line)
    _paint_filled_vertices(
        painter=painter,
        path=paths.vertices,
        highlighted=context.highlight is not None,
        palette=palette,
    )
    _paint_filled_vertices(
        painter=painter,
        path=paths.rotation_vertices,
        highlighted=context.rotation_highlight is not None,
        palette=palette,
    )
    if context.fill and shape.shape_type not in ["line", "linestrip", "points", "mask"]:
        fill = palette.select_fill if context.selected else palette.fill
        painter.fillPath(paths.line, fill)
    if paths.orientation_arrow.length() > 0:
        arrow_pen = QtGui.QPen(palette.vertex_fill)
        arrow_pen.setWidth(PEN_WIDTH)
        painter.setPen(arrow_pen)
        painter.drawPath(paths.orientation_arrow)

    if paths.negative_vertices.length() > 0:
        neg_color = QtGui.QColor(255, 0, 0, 255)
        neg_pen = QtGui.QPen(neg_color)
        neg_pen.setWidth(PEN_WIDTH)
        painter.setPen(neg_pen)
        painter.drawPath(paths.negative_vertices)
        painter.fillPath(paths.negative_vertices, neg_color)


def _paint_filled_vertices(
    *,
    painter: QtGui.QPainter,
    path: QtGui.QPainterPath,
    highlighted: bool,
    palette: Palette,
) -> None:
    if path.length() == 0:
        return
    fill = palette.hvertex_fill if highlighted else palette.vertex_fill
    painter.drawPath(path)
    painter.fillPath(path, fill)


def _resolve_vertex_style(
    *,
    highlight: VertexHighlight | None,
    vertex_index: int,
    default_size: int,
    default_point_type: Literal["square", "round"],
) -> tuple[float, Literal["square", "round"]]:
    if highlight is not None and highlight.index == vertex_index:
        return default_size * highlight.size_factor, highlight.point_type
    return default_size, default_point_type


def _build_shape_point_path(
    *,
    path: QtGui.QPainterPath,
    shape: Shape,
    context: ShapeRenderContext,
    vertex_index: int,
) -> None:
    size, point_type = _resolve_vertex_style(
        highlight=context.highlight,
        vertex_index=vertex_index,
        default_size=context.point_size,
        default_point_type=context.point_type,
    )
    pos = QtCore.QPointF(*(shape.points[vertex_index] * context.scale))
    _draw_vertex(path=path, pos=pos, size=size, point_type=point_type)


def _build_shape_rotation_point_path(
    *,
    path: QtGui.QPainterPath,
    shape: Shape,
    context: ShapeRenderContext,
    vertex_index: int,
) -> None:
    size, point_type = _resolve_vertex_style(
        highlight=context.rotation_highlight,
        vertex_index=vertex_index,
        default_size=context.point_size,
        default_point_type=context.point_type,
    )
    handle = get_rotation_handle(shape=shape, index=vertex_index)
    pos = QtCore.QPointF(*(handle * context.scale))
    _draw_vertex(path=path, pos=pos, size=size, point_type=point_type)


def _draw_vertex(
    *,
    path: QtGui.QPainterPath,
    pos: QtCore.QPointF,
    size: float,
    point_type: Literal["square", "round"],
) -> None:
    half = size / 2.0
    if point_type == "square":
        path.addRect(pos.x() - half, pos.y() - half, size, size)
    elif point_type == "round":
        path.addEllipse(pos, half, half)
    else:
        raise ValueError(f"Unsupported vertex shape: {point_type}")


def _build_shape_oriented_rectangle_arrow_path(
    *, path: QtGui.QPainterPath, shape: Shape, scale: float
) -> None:
    points = oriented_rectangle_arrow_points(shape=shape)
    head_right, tip, head_left, tail = (QtCore.QPointF(*(p * scale)) for p in points)
    path.moveTo(head_right)
    path.lineTo(tip)
    path.lineTo(head_left)
    path.moveTo(tail)
    path.lineTo(tip)


def _build_shape_points_paths(
    *,
    shape: Shape,
    context: ShapeRenderContext,
) -> _ShapePaths:
    paths = _ShapePaths()
    scale = context.scale
    points = shape.points
    if shape.shape_type in ["rectangle", "mask"]:
        if len(points) not in (1, 2):
            logger.warning(
                "Unexpected point count for shape type '{}': got {}, expected 1-2",
                shape.shape_type,
                len(points),
            )
            return paths
        if len(points) == 2:
            paths.line.addRect(
                QtCore.QRectF(
                    QtCore.QPointF(*(points[0] * scale)),
                    QtCore.QPointF(*(points[1] * scale)),
                )
            )
        if shape.shape_type == "rectangle":
            for i in range(len(points)):
                _build_shape_point_path(
                    path=paths.vertices, shape=shape, context=context, vertex_index=i
                )
    elif shape.shape_type == "oriented_rectangle":
        if len(points) not in (1, 2, 4):
            logger.warning(
                "Unexpected point count for shape type 'oriented_rectangle': "
                "got {}, expected 1, 2, or 4",
                len(points),
            )
            return paths
        if len(points) == 4:
            paths.line.moveTo(QtCore.QPointF(*(points[0] * scale)))
            for i in range(len(points)):
                paths.line.lineTo(QtCore.QPointF(*(points[i] * scale)))
                _build_shape_point_path(
                    path=paths.vertices, shape=shape, context=context, vertex_index=i
                )
            paths.line.lineTo(QtCore.QPointF(*(points[0] * scale)))
            for i in range(len(points)):
                _build_shape_rotation_point_path(
                    path=paths.rotation_vertices,
                    shape=shape,
                    context=context,
                    vertex_index=i,
                )
            _build_shape_oriented_rectangle_arrow_path(
                path=paths.orientation_arrow, shape=shape, scale=scale
            )
        elif len(points) == 2:
            paths.line.moveTo(QtCore.QPointF(*(points[0] * scale)))
            paths.line.lineTo(QtCore.QPointF(*(points[1] * scale)))
            for i in range(2):
                _build_shape_point_path(
                    path=paths.vertices, shape=shape, context=context, vertex_index=i
                )
    elif shape.shape_type == "circle":
        if len(points) not in (1, 2):
            logger.warning(
                "Unexpected point count for shape type 'circle': got {}, expected 1-2",
                len(points),
            )
            return paths
        if len(points) == 2:
            radius = float(np.linalg.norm((points[0] - points[1]) * scale))
            paths.line.addEllipse(QtCore.QPointF(*(points[0] * scale)), radius, radius)
        for i in range(len(points)):
            _build_shape_point_path(
                path=paths.vertices, shape=shape, context=context, vertex_index=i
            )
    elif shape.shape_type == "linestrip":
        paths.line.moveTo(QtCore.QPointF(*(points[0] * scale)))
        for i in range(len(points)):
            paths.line.lineTo(QtCore.QPointF(*(points[i] * scale)))
            _build_shape_point_path(
                path=paths.vertices, shape=shape, context=context, vertex_index=i
            )
    elif shape.shape_type == "points":
        assert len(points) == len(shape.point_labels)
        for i, point_label in enumerate(shape.point_labels):
            path = paths.vertices if point_label == 1 else paths.negative_vertices
            _build_shape_point_path(
                path=path, shape=shape, context=context, vertex_index=i
            )
    else:
        paths.line.moveTo(QtCore.QPointF(*(points[0] * scale)))
        for i in range(len(points)):
            paths.line.lineTo(QtCore.QPointF(*(points[i] * scale)))
            _build_shape_point_path(
                path=paths.vertices, shape=shape, context=context, vertex_index=i
            )
        if shape.closed:
            paths.line.lineTo(QtCore.QPointF(*(points[0] * scale)))
    return paths


def is_hit_by_point(
    *,
    shape: Shape,
    point: npt.NDArray[np.float64],
    scale: float,
    point_size: int,
    epsilon: float,
) -> bool:
    if shape.shape_type in ("line", "linestrip"):
        return (
            nearest_edge_index(shape=shape, point=point, scale=scale, epsilon=epsilon)
            is not None
        )
    if shape.shape_type == "points":
        return False
    if shape.shape_type == "point":
        if len(shape.points) == 0:
            return False
        return bool(np.linalg.norm((point - shape.points[0]) * scale) <= point_size / 2)
    if shape.mask is not None:
        raw_y = int(round(float(point[1]) - float(shape.points[0][1])))
        raw_x = int(round(float(point[0]) - float(shape.points[0][0])))
        if (
            raw_y < 0
            or raw_y >= shape.mask.shape[0]
            or raw_x < 0
            or raw_x >= shape.mask.shape[1]
        ):
            return False
        return bool(shape.mask[raw_y, raw_x])
    return _build_image_path(shape=shape).contains(QtCore.QPointF(*point))


def bounds(*, shape: Shape) -> QtCore.QRectF:
    return _build_image_path(shape=shape).boundingRect()


def _build_image_path(*, shape: Shape) -> QtGui.QPainterPath:
    points = shape.points
    out = QtGui.QPainterPath()
    if shape.shape_type in ("rectangle", "mask"):
        if len(points) == 2:
            out.addRect(
                QtCore.QRectF(QtCore.QPointF(*points[0]), QtCore.QPointF(*points[1]))
            )
    elif shape.shape_type == "circle":
        if len(points) == 2:
            radius = float(np.linalg.norm(points[0] - points[1]))
            out.addEllipse(QtCore.QPointF(*points[0]), radius, radius)
    elif shape.shape_type == "oriented_rectangle":
        if len(points) == 4:
            out.moveTo(QtCore.QPointF(*points[0]))
            for p in points[1:]:
                out.lineTo(QtCore.QPointF(*p))
            out.lineTo(QtCore.QPointF(*points[0]))
    else:
        if len(points) > 0:
            out.moveTo(QtCore.QPointF(*points[0]))
            for p in points[1:]:
                out.lineTo(QtCore.QPointF(*p))
    return out


def _paint_shape_description(
    *,
    painter: QtGui.QPainter,
    shape: Shape,
    context: ShapeRenderContext,
) -> None:
    """Paint shape description text near the shape's bounding box.

    Positions the text above the shape, shifting left/right/down if needed
    to keep it within the image boundaries.
    """
    if not shape.description or len(shape.points) == 0:
        return

    scaled_points = shape.points * context.scale
    min_xy = scaled_points.min(axis=0)
    max_xy = scaled_points.max(axis=0)
    rect_left = float(min_xy[0])
    rect_top = float(min_xy[1])
    rect_right = float(max_xy[0])
    rect_bottom = float(max_xy[1])
    rect_w = rect_right - rect_left
    rect_h = rect_bottom - rect_top

    if rect_w <= 0 or rect_h <= 0:
        return

    # Font size proportional to image scale so text stays in natural
    # proportion to shapes across all image sizes and zoom levels.
    # At scale=1.0 (image fits viewport), the target is ~14 px.
    viewport = painter.viewport()
    font_size = max(10, min(25, int(round(14.0 * context.scale))))
    font = QtGui.QFont("Arial", font_size)
    painter.setFont(font)

    fm = QtGui.QFontMetrics(font)
    text_rect = fm.tightBoundingRect(shape.description)
    padding_x = 6
    padding_y = 4
    bg_w = text_rect.width() + 2 * padding_x
    bg_h = text_rect.height() + 2 * padding_y

    # Default: above the shape
    x = rect_left
    y = rect_top - bg_h - 2

    # Estimate image dimensions from painter viewport for boundary clamping.
    img_w = viewport.width()
    img_h = viewport.height()

    # If above is out of bounds, try left side
    if y < 0:
        gap = 1
        x = rect_left - bg_w - gap
        y = rect_top
        if x < 0:
            x = rect_right + gap
            if x + bg_w > img_w:
                x = rect_left
                y = rect_bottom + gap

    # Final boundary clamp
    x = max(0.0, min(x, img_w - bg_w))
    y = max(0.0, min(y, img_h - bg_h))

    # Background color from shape's line color
    bg_color = QtGui.QColor(context.palette.line)
    bg_color.setAlpha(200)

    # Auto-select white or black text based on background brightness
    brightness = (
        bg_color.red() * 0.299
        + bg_color.green() * 0.587
        + bg_color.blue() * 0.114
    )
    text_color = QtGui.QColor(0, 0, 0) if brightness > 128 else QtGui.QColor(255, 255, 255)

    # Save/restore painter to avoid leaking brush to subsequent shapes.
    painter.save()
    try:
        # Draw rounded rectangle background
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(bg_color)
        painter.drawRoundedRect(x, y, bg_w, bg_h, 4, 4)

        # Draw text centered
        painter.setPen(text_color)
        painter.drawText(QtCore.QRectF(x, y, bg_w, bg_h), QtCore.Qt.AlignCenter, shape.description)
    finally:
        painter.restore()
