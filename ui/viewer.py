from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap, QTransform
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView


class ImageView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)

        self.setRenderHints(self.renderHints() | QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)

    def set_pixmap(self, pm: QPixmap, preserve_view: bool = False):
        had_previous = not self._pixmap_item.pixmap().isNull()
        old_transform = self.transform()
        old_h = self.horizontalScrollBar().value()
        old_v = self.verticalScrollBar().value()
        self._pixmap_item.setPixmap(pm)
        self._scene.setSceneRect(pm.rect())
        if preserve_view and had_previous:
            self.setTransform(old_transform)
            self.horizontalScrollBar().setValue(old_h)
            self.verticalScrollBar().setValue(old_v)
        else:
            self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def clear_image(self):
        self._pixmap_item.setPixmap(QPixmap())
        self._scene.setSceneRect(0, 0, 1, 1)

    def set_image(self, path):
        if not path or not path.exists():
            self.clear_image()
            return
        pm = QPixmap(str(path))
        self.set_pixmap(pm, preserve_view=False)

    def wheelEvent(self, event):
        factor = 1.20 if event.angleDelta().y() > 0 else 1 / 1.20
        self.scale(factor, factor)

    def fit_to_view(self):
        if self._pixmap_item.pixmap().isNull():
            return
        self.fitInView(self._scene.sceneRect(), Qt.KeepAspectRatio)

    def set_zoom_100(self):
        if self._pixmap_item.pixmap().isNull():
            return
        self.setTransform(QTransform())
        self.centerOn(self._scene.sceneRect().center())

