from PyQt5.QtCore import QRectF, QPointF, Qt
from PyQt5.QtGui import QImage, QPainter, QPixmap, QMouseEvent, QWheelEvent
from PyQt5.QtWidgets import QApplication, QMenu, QAction, QFileDialog, QWidget
from logging_functions import print_to_log, log_function_call


class ImageViewer(QWidget):
    """
    A widget for displaying and interacting with images.
    ...
    """

    @log_function_call
    def __init__(self, parent=None) -> None:
        """
        Initialize the ImageViewer widget.

        :param parent: The parent widget.
        :type parent: QWidget
        :return: None
        :rtype: None
        """
        """
        Initialize the ImageViewer widget.

        Args:
            parent (QWidget): The parent widget.

        Returns:
            None
        """
        super(ImageViewer, self).__init__(parent)
        self.image = QImage()
        self.pixmap = QPixmap()
        self.rect = QRectF()
        self.dragPos = QPointF()
        self.dragging = False
        self.zoom_factor = 1.0
        self.min_zoom = 0.1  # Minimum zoom factor
        self.max_zoom = 10.0  # Maximum zoom factor
        # Set minimum size for the widget
        self.setMinimumSize(256, 256)

    @log_function_call
    def clear_image(self) -> None:
        """
        Clear the currently displayed image.

        :return: None
        :rtype: None
        """
        self.image = QImage()  # Reset the QImage object
        self.pixmap = QPixmap()  # Reset the QPixmap object
        self.update()  # Trigger a repaint of the widget

    @log_function_call
    def load_image(self, image_path: str) -> None:
        """
        Load an image from the specified file path.

        :param image_path: The path to the image file.
        :type image_path: str
        :return: None
        :rtype: None
        """
        self.image.load(image_path)
        self.load_qimage(self.image)

    @log_function_call
    def load_qimage(self, qimage: QImage) -> None:
        """
        Load an image from a QImage object.

        :param qimage: The QImage to load.
        :type qimage: QImage
        :return: None
        :rtype: None
        """
        self.image = qimage
        self.pixmap = QPixmap.fromImage(self.image)
        self.fit_image()
        self.update()

    @log_function_call
    def fit_image(self) -> None:
        """
        Fit the image within the widget's dimensions.

        :return: None
        :rtype: None
        """
        widget_width = self.width()
        widget_height = self.height()

        img_width = self.image.width()
        img_height = self.image.height()

        # Check if an image is loaded and the widget has non-zero dimensions
        if img_width > 0 and img_height > 0 and widget_width > 0 and widget_height > 0:
            # Calculate the zoom factor
            self.zoom_factor = min(widget_width / img_width, widget_height / img_height)

            # Calculate new image dimensions
            width = img_width * self.zoom_factor
            height = img_height * self.zoom_factor

            # Calculate position to center image
            x = (widget_width - width) / 2.0
            y = (widget_height - height) / 2.0

            self.rect = QRectF(x, y, width, height)

    def paintEvent(self, event) -> None:
        """
        Handle painting the image on the widget.

        :param event: The paint event.
        :type event: QPaintEvent
        :return: None
        :rtype: None
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        painter.save()
        painter.translate(self.rect.topLeft())
        painter.scale(self.zoom_factor, self.zoom_factor)
        painter.drawPixmap(0, 0, self.pixmap)
        painter.restore()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse button press events.

        :param event: The mouse event.
        :type event: QMouseEvent
        :return: None
        :rtype: None
        """
        if event.button() == Qt.LeftButton:
            self.dragging = True
            self.dragPos = event.pos() - self.rect.topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse move events (e.g., dragging the image).

        :param event: The mouse event.
        :type event: QMouseEvent
        :return: None
        :rtype: None
        #"""
        if self.dragging:
            self.rect.moveTopLeft(event.pos() - self.dragPos)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """
        Handle mouse button release events.

        :param event: The mouse event.
        :type event: QMouseEvent
        :return: None
        :rtype: None
        """
        self.dragging = False

    def wheelEvent(self, event: QWheelEvent) -> None:
        """
        Handle wheel events (e.g., zooming).

        :param event: The wheel event.
        :type event: QWheelEvent
        :return: None
        :rtype: None
        """
        pos = event.position()
        zoomInFactor = 1.05
        zoomOutFactor = 1 / zoomInFactor

        if event.angleDelta().y() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor

        self.zoom(pos, zoomFactor)

    def resizeEvent(self, event) -> None:
        """
        Update the zoom and position when the widget is resized.

        :param event: The resize event.
        :type event: QResizeEvent
        :return: None
        :rtype: None
        """
        self.fit_image()
        self.update()

    def zoom(self, position: QPointF, factor: float) -> None:
        """
        Zoom in or out on the image.

        :param position: The zoom center position.
        :type position: QPointF
        :param factor: The zoom factor.
        :type factor: float
        :return: None
        :rtype: None
        """
        new_zoom = self.zoom_factor * factor

        if self.min_zoom <= new_zoom <= self.max_zoom:
            self.zoom_factor = new_zoom
            self.rect.moveTopLeft(position - (position - self.rect.topLeft()) * factor)
            self.update()

    def enterEvent(self, event) -> None:
        """
        Handle the mouse entering the widget (set cursor).

        :param event: The mouse enter event.
        :type event: QEvent
        :return: None
        :rtype: None
        """
        QApplication.setOverrideCursor(Qt.OpenHandCursor)

    def leaveEvent(self, event) -> None:
        """
        Handle the mouse leaving the widget (restore cursor).

        :param event: The mouse leave event.
        :type event: QEvent
        :return: None
        :rtype: None
        """
        QApplication.restoreOverrideCursor()

    @log_function_call
    def contextMenuEvent(self, event) -> None:
        """
        Handle the context menu event.

        :param event: The context menu event.
        :type event: QContextMenuEvent
        :return: None
        :rtype: None
        """
        contextMenu = QMenu(self)

        copyAction = QAction("Copy", self)
        copyAction.triggered.connect(self.copy_image_to_clipboard)

        saveAsAction = QAction("Save As", self)
        saveAsAction.triggered.connect(self.save_image_as)

        contextMenu.addAction(copyAction)
        contextMenu.addAction(saveAsAction)

        contextMenu.exec_(event.globalPos())

    @log_function_call
    def copy_image_to_clipboard(self) -> None:
        """
        Copy the image to the clipboard.

        :return: None
        :rtype: None
        """
        clipboard = QApplication.clipboard()
        clipboard.setPixmap(self.pixmap)

    @log_function_call
    def save_image_as(self) -> None:
        """
        Save the image to a file.

        :return: None
        :rtype: None
        """
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        filePath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Image As",
            "",
            "PNG Files (*.png);;JPEG Files (*.jpeg *.jpg);;All Files (*)",
            options=options,
        )
        if filePath:
            self.image.save(filePath)
