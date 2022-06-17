# Copyright (c) 2009-2010 LOGILAB S.A. (Paris, FRANCE).
# http://www.logilab.fr/ -- mailto:contact@logilab.fr
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from __future__ import absolute_import

from .qtcore import (
    QModelIndex,
    Qt,
    pyqtSignal,
    pyqtSlot,
)
from .qtgui import (
    QAbstractItemView,
    QTreeView,
)

from ..util import hglib
from . import (
    manifestmodel,
    qtlib,
)

if hglib.TYPE_CHECKING:
    from typing import (
        List,
        Optional,
    )
    from .qtgui import (
        QWidget,
    )


class HgFileListView(QTreeView):
    """Display files and statuses between two revisions or patch"""

    fileSelected = pyqtSignal(str, str)
    clearDisplay = pyqtSignal()

    def __init__(self, parent):
        # type: (Optional[QWidget]) -> None
        QTreeView.__init__(self, parent)
        self.setHeaderHidden(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setRootIsDecorated(False)
        self.setTextElideMode(Qt.ElideLeft)

        # give consistent height and enable optimization
        self.setIconSize(qtlib.smallIconSize())
        self.setUniformRowHeights(True)

    def _model(self):
        # type: () -> manifestmodel.ManifestModel
        model = self.model()
        assert isinstance(model, manifestmodel.ManifestModel)
        return model

    def setModel(self, model):
        # type: (manifestmodel.ManifestModel) -> None
        QTreeView.setModel(self, model)
        model.layoutChanged.connect(self._onLayoutChanged)
        model.revLoaded.connect(self._onRevLoaded)
        self.selectionModel().currentRowChanged.connect(self._emitFileChanged)

    def currentFile(self):
        # type: () -> bytes
        index = self.currentIndex()
        model = self._model()
        return hglib.fromunicode(model.filePath(index))

    def setCurrentFile(self, path):
        # type: (bytes) -> None
        model = self._model()
        model.fetchMore(QModelIndex())  # make sure path is populated
        self.setCurrentIndex(model.indexFromPath(hglib.tounicode(path)))

    def getSelectedFiles(self):
        # type: () -> List[bytes]
        model = self._model()
        return [hglib.fromunicode(model.filePath(index))
                for index in self.selectedRows()]

    def _initCurrentIndex(self):
        # type: () -> None
        m = self._model()
        if m.rowCount() > 0:
            self.setCurrentIndex(m.index(0, 0))
        else:
            self.clearDisplay.emit()

    @pyqtSlot()
    def _onLayoutChanged(self):
        # type: () -> None
        index = self.currentIndex()
        if index.isValid():
            self.scrollTo(index)
            return
        self._initCurrentIndex()

    @pyqtSlot()
    def _onRevLoaded(self):
        # type: () -> None
        index = self.currentIndex()
        if index.isValid():
            # redisplay previous row
            self._emitFileChanged()
        else:
            self._initCurrentIndex()

    @pyqtSlot()
    def _emitFileChanged(self):
        # type: () -> None
        index = self.currentIndex()
        m = self._model()
        if index.isValid():
            # TODO: delete status from fileSelected because it isn't primitive
            # pseudo directory node has no status
            st = m.fileStatus(index) or ''
            self.fileSelected.emit(m.filePath(index), st)
        else:
            self.clearDisplay.emit()

    def selectedRows(self):
        # type: () -> List[QModelIndex]
        return self.selectionModel().selectedRows()
