# hgignore.py - TortoiseHg's dialog for editing .hgignore
#
# Copyright 2010 Steve Borho <steve@borho.org>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2, incorporated herein by reference.

from __future__ import absolute_import

import os
import re

from .qtcore import (
    QEvent,
    QSettings,
    QTimer,
    Qt,
    pyqtSignal,
)
from .qtgui import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QPushButton,
    QSplitter,
    QVBoxLayout,
)

from hgext.largefiles import (
    lfutil,
)

from mercurial import (
    commands,
    error,
    match,
    util,
)

from ..util import (
    hglib,
    shlib,
)
from ..util.i18n import _
from . import (
    qscilib,
    qtlib,
)

class HgignoreDialog(QDialog):
    'Edit a repository .hgignore file'

    ignoreFilterUpdated = pyqtSignal()

    contextmenu = None

    def __init__(self, repoagent, parent=None, *pats):
        'Initialize the Dialog'
        QDialog.__init__(self, parent)
        self.setWindowFlags(self.windowFlags()
            & ~Qt.WindowContextHelpButtonHint
            | Qt.WindowMaximizeButtonHint)

        self._repoagent = repoagent
        self.pats = pats
        self.setWindowTitle(_('Ignore filter - %s') % repoagent.displayName())
        self.setWindowIcon(qtlib.geticon('thg-ignore'))

        vbox = QVBoxLayout()
        self.setLayout(vbox)

        # layer 1
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        recombo = QComboBox()
        recombo.addItems([_('Glob'), _('Regexp')])
        hbox.addWidget(recombo)

        le = QLineEdit()
        hbox.addWidget(le, 1)
        le.returnPressed.connect(self.addEntry)

        add = QPushButton(_('Add'))
        add.setAutoDefault(False)
        add.clicked.connect(self.addEntry)
        hbox.addWidget(add, 0)

        # layer 2
        repo = repoagent.rawRepo()
        hbox = QHBoxLayout()
        vbox.addLayout(hbox)
        ignorefiles = [repo.wjoin(b'.hgignore')]
        for name, value in repo.ui.configitems(b'ui'):
            if name == b'ignore' or name.startswith(b'ignore.'):
                ignorefiles.append(util.expandpath(value))

        filecombo = QComboBox()
        hbox.addWidget(filecombo)
        for f in ignorefiles:
            filecombo.addItem(hglib.tounicode(f))
        filecombo.currentIndexChanged.connect(self.fileselect)
        self.ignorefile = ignorefiles[0]

        edit = QPushButton(_('Edit File'))
        edit.setAutoDefault(False)
        edit.clicked.connect(self.editClicked)
        hbox.addWidget(edit)
        hbox.addStretch(1)

        # layer 3 - main widgets
        split = QSplitter()
        vbox.addWidget(split, 1)

        ignoregb = QGroupBox()
        ivbox = QVBoxLayout()
        ignoregb.setLayout(ivbox)
        lbl = QLabel(_('<b>Ignore Filter</b>'))
        ivbox.addWidget(lbl)
        split.addWidget(ignoregb)

        unknowngb = QGroupBox()
        uvbox = QVBoxLayout()
        unknowngb.setLayout(uvbox)
        lbl = QLabel(_('<b>Untracked Files</b>'))
        uvbox.addWidget(lbl)
        split.addWidget(unknowngb)

        ignorelist = QListWidget()
        ivbox.addWidget(ignorelist)
        ignorelist.setSelectionMode(QAbstractItemView.ExtendedSelection)
        unknownlist = QListWidget()
        uvbox.addWidget(unknownlist)
        unknownlist.setSelectionMode(QAbstractItemView.ExtendedSelection)
        unknownlist.currentTextChanged.connect(self.setGlobFilter)
        unknownlist.setContextMenuPolicy(Qt.CustomContextMenu)
        unknownlist.customContextMenuRequested.connect(self.menuRequest)
        unknownlist.itemDoubleClicked.connect(self.unknownDoubleClicked)
        lbl = QLabel(_('Backspace or Del to remove row(s)'))
        ivbox.addWidget(lbl)

        # layer 4 - dialog buttons
        BB = QDialogButtonBox
        bb = QDialogButtonBox(BB.Close)
        bb.button(BB.Close).setAutoDefault(False)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        vbox.addWidget(bb)
        self.bb = bb

        le.setFocus()
        self.le, self.recombo, self.filecombo = le, recombo, filecombo
        self.ignorelist, self.unknownlist = ignorelist, unknownlist
        ignorelist.installEventFilter(self)
        QTimer.singleShot(0, self.refresh)

        s = QSettings()
        self.restoreGeometry(qtlib.readByteArray(s, 'hgignore/geom'))

    @property
    def repo(self):
        return self._repoagent.rawRepo()

    def eventFilter(self, obj, event):
        if obj != self.ignorelist:
            return False
        if event.type() != QEvent.KeyPress:
            return False
        elif event.key() not in (Qt.Key_Backspace, Qt.Key_Delete):
            return False
        if obj.currentRow() < 0:
            return False
        for idx in sorted(obj.selectedIndexes(), reverse=True):
            self.ignorelines.pop(idx.row())
        self.writeIgnoreFile()
        self.refresh()
        return True

    def menuRequest(self, point):
        'context menu request for unknown list'
        point = self.unknownlist.viewport().mapToGlobal(point)
        selected = [self.lclunknowns[i.row()]
                    for i in sorted(self.unknownlist.selectedIndexes())]
        if len(selected) == 0:
            return
        if not self.contextmenu:
            self.contextmenu = QMenu(self)
            self.contextmenu.setTitle(_('Add ignore filter...'))
        else:
            self.contextmenu.clear()
        filters = []
        if len(selected) == 1:
            local = selected[0]
            filters.append([local])
            dirname = os.path.dirname(local)
            while dirname:
                filters.append([dirname])
                dirname = os.path.dirname(dirname)
            base, ext = os.path.splitext(local)
            if ext:
                ext = hglib.tounicode(ext)
                filters.append(['*'+ext])
                filters.append(['**'+ext])
        else:
            filters.append(selected)
        for f in filters:
            n = len(f) == 1 and f[0] or _('selected files')
            a = self.contextmenu.addAction(_('Ignore ') + hglib.tounicode(n))
            a._patterns = f
            a.triggered.connect(self.insertFilters)
        self.contextmenu.exec_(point)

    def unknownDoubleClicked(self, item):
        self.insertFilters([hglib.fromunicode(item.text())])

    def insertFilters(self, pats=None, isregexp=False):
        if not pats:
            pats = self.sender()._patterns
        h = isregexp and b'syntax: regexp' or b'syntax: glob'
        if h in self.ignorelines:
            l = self.ignorelines.index(h)
            for i, line in enumerate(self.ignorelines[l+1:]):
                if line.startswith(b'syntax:'):
                    for pat in pats:
                        self.ignorelines.insert(l+i+1, pat)
                    break
            else:
                self.ignorelines.extend(pats)
        else:
            self.ignorelines.append(h)
            self.ignorelines.extend(pats)
        self.writeIgnoreFile()
        self.refresh()

    def setGlobFilter(self, qstr):
        'user selected an unknown file; prep a glob filter'
        self.recombo.setCurrentIndex(0)
        self.le.setText(qstr)

    def fileselect(self):
        'user selected another ignore file'
        self.ignorefile = hglib.fromunicode(self.filecombo.currentText())
        self.refresh()

    def editClicked(self):
        ignfile = hglib.tounicode(self.ignorefile)
        if qscilib.fileEditor(ignfile) == QDialog.Accepted:
            self.refresh()

    def addEntry(self):
        newfilter = hglib.fromunicode(self.le.text()).strip()
        if newfilter == b'':
            return
        self.le.clear()
        if self.recombo.currentIndex() == 0:
            test = b'glob:' + newfilter
            try:
                match.match(self.repo.root, b'', [], [test])
                self.insertFilters([newfilter], False)
            except error.Abort as inst:
                qtlib.WarningMsgBox(_('Invalid glob expression'), str(inst),
                                    parent=self)
                return
        else:
            test = b'relre:' + newfilter
            try:
                match.match(self.repo.root, b'', [], [test])
                re.compile(test)
                self.insertFilters([newfilter], True)
            except (error.Abort, re.error) as inst:
                qtlib.WarningMsgBox(_('Invalid regexp expression'), str(inst),
                                    parent=self)
                return

    def refresh(self):
        try:
            with open(self.ignorefile, 'rb') as fp:
                l = fp.readlines()
            self.doseoln = l[0].endswith(b'\r\n')
        except (IOError, ValueError, IndexError):
            self.doseoln = os.name == 'nt'
            l = []
        self.ignorelines = [line.strip() for line in l]
        self.ignorelist.clear()

        uni = hglib.tounicode

        self.ignorelist.addItems([uni(l) for l in self.ignorelines])

        try:
            self.repo.thginvalidate()
            with lfutil.lfstatus(self.repo):
                self.lclunknowns = self.repo.status(unknown=True).unknown
        except (EnvironmentError, error.RepoError) as e:
            qtlib.WarningMsgBox(_('Unable to read repository status'),
                                uni(str(e)), parent=self)
        except error.Abort as e:
            if e.hint:
                err = _('%s (hint: %s)') % (uni(str(e)), uni(e.hint))
            else:
                err = uni(str(e))
            qtlib.WarningMsgBox(_('Unable to read repository status'),
                                err, parent=self)
            self.lclunknowns = []
            return

        if not self.pats:
            try:
                self.pats = [self.lclunknowns[i.row()]
                         for i in self.unknownlist.selectedIndexes()]
            except IndexError:
                self.pats = []
        self.unknownlist.clear()
        self.unknownlist.addItems([uni(u) for u in self.lclunknowns])
        for i, u in enumerate(self.lclunknowns):
            if u in self.pats:
                item = self.unknownlist.item(i)
                item.setSelected(True)
                self.unknownlist.setCurrentItem(item)
                self.le.setText(hglib.tounicode(u))
        self.pats = []

    def writeIgnoreFile(self):
        eol = self.doseoln and b'\r\n' or b'\n'
        out = eol.join(self.ignorelines) + eol
        hasignore = os.path.exists(self.repo.vfs.join(self.ignorefile))

        try:
            f = util.atomictempfile(self.ignorefile, b'wb', createmode=None)
            f.write(out)
            f.close()
            if not hasignore:
                ret = qtlib.QuestionMsgBox(_('New file created'),
                                           _('TortoiseHg has created a new '
                                             '.hgignore file.  Would you like to '
                                             'add this file to the source code '
                                             'control repository?'), parent=self)
                if ret:
                    commands.add(hglib.loadui(), self.repo, self.ignorefile)
            shlib.shell_notify([self.ignorefile])
            self.ignoreFilterUpdated.emit()
        except EnvironmentError as e:
            qtlib.WarningMsgBox(_('Unable to write .hgignore file'),
                                hglib.tounicode(str(e)), parent=self)

    def accept(self):
        s = QSettings()
        s.setValue('hgignore/geom', self.saveGeometry())
        QDialog.accept(self)

    def reject(self):
        s = QSettings()
        s.setValue('hgignore/geom', self.saveGeometry())
        QDialog.reject(self)
