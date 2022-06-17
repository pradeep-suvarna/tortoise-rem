# close_branch.py - Close branch dialog for TortoiseHg
#
# Copyright 2020 Bram Belpaire <belpairebram@hotmail.com>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2, incorporated herein by reference.

from __future__ import absolute_import

from mercurial import (
    pycompat,
)

from .qtgui import (
    QSizePolicy,
    QLineEdit,
    QFormLayout,
    QLabel
)

from ..util import (
    hglib,
    i18n,
)
from ..util.i18n import _
from . import (
    cmdui,
)

if hglib.TYPE_CHECKING:
    from typing import (
        List,
        Optional,
        Text,
    )
    from .qtgui import (
        QWidget,
    )
    from .cmdcore import (
        CmdSession,
    )
    from .thgrepo import (
        RepoAgent,
    )


class CloseWidget(cmdui.AbstractCmdWidget):
    def __init__(self, repoagent, rev, parent=None):
        # type: (RepoAgent, int, Optional[QWidget]) -> None
        super(CloseWidget, self).__init__(parent)
        self._repoagent = repoagent
        self._repo = repoagent.rawRepo()
        self._rev = rev
        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        # simple widget with only an editable commit message textbox
        self.setLayout(form)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        # add revision information about selected revision
        form.addRow(_('Revision:'), QLabel('%d (%s)' % (rev, self._repo[rev])))
        # commit message
        self.hg_commit = QLineEdit()
        # automatic message
        msgset = i18n.keepgettext()._('Close %s branch')
        str_msg = msgset['str']
        self.hg_commit.setText(pycompat.unicode(str_msg) %
                               hglib.tounicode(self._repo[self._rev].branch()))
        form.addRow(_('Commit message:'), self.hg_commit)

    def compose_command(self):
        # type: () -> List[Text]
        rev = '%d' % self._rev
        cmdline = hglib.buildcmdargs('close-head', m=self.hg_commit.text(),
                                     r=rev)
        return cmdline

    def runCommand(self):
        # type: () -> CmdSession
        cmdline = self.compose_command()
        return self._repoagent.runCommand(cmdline, self)

    def canRunCommand(self):
        # type: () -> bool
        return True

def createCloseBranchDialog(repoagent, rev, parent):
    # type: (RepoAgent, int, Optional[QWidget]) -> cmdui.CmdControlDialog
    dlg = cmdui.CmdControlDialog(parent)
    dlg.setWindowTitle(_('Close Branch - %s') % repoagent.displayName())
    dlg.setRunButtonText(_('&Close Branch'))
    dlg.setCommandWidget(CloseWidget(repoagent, rev, dlg))
    return dlg
