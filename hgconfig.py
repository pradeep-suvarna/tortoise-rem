# hgconfig.py - unicode wrapper for Mercurial's ui object
#
# Copyright 2019 Yuya Nishihara <yuya@tcha.org>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

from __future__ import absolute_import

from mercurial import (
    encoding,
    pycompat,
    ui as uimod,
)

from ..util import (
    hglib,
)

if hglib.TYPE_CHECKING:
    from typing import (
        List,
        Text,
        Tuple,
    )

UNSET_DEFAULT = uimod._unset

class HgConfig(object):
    """Unicode wrapper for Mercurial's ui object

    This provides Qt-like API on top of the ui object. Almost all methods
    are proxied through RepoAgent. Use these methods unless necessary.

    All config*() getter functions never return None, nor take None as
    default value. That's because Qt C++ API is strict about data types
    in general. Use hasConfig() to test if the config value is set.
    """

    # Design notes:
    # - It's probably better to fetch bytes data from ui at once, and cache
    #   the unicode representation in this object. We'll have to be careful
    #   to keep the data sync with the underlying ui object.
    # - No setter functions are provided right now because we can't propagate
    #   new values to the command process.

    def __init__(self, ui):
        # type: (uimod.ui) -> None
        self._ui = ui

    def rawUi(self):
        # type: () -> uimod.ui
        return self._ui

    def configBool(self, section, name, default=UNSET_DEFAULT):
        # type: (Text, Text, bool) -> bool
        data = self._ui.configbool(_tobytes(section), _tobytes(name),
                                   default=default)
        return bool(data)

    def configInt(self, section, name, default=UNSET_DEFAULT):
        # type: (Text, Text, int) -> int
        data = self._ui.configint(_tobytes(section), _tobytes(name),
                                  default=default)
        return int(data)

    def configString(self, section, name, default=UNSET_DEFAULT):
        # type: (Text, Text, Text) -> Text
        if default is not UNSET_DEFAULT:
            default = _tobytes(default)
        data = self._ui.config(_tobytes(section), _tobytes(name),
                               default=default)
        if data is None:
            return ''
        return _tostr(data)

    def configStringList(self, section, name, default=UNSET_DEFAULT):
        # type: (Text, Text, List[Text]) -> List[Text]
        if default is not UNSET_DEFAULT:
            default = pycompat.maplist(_tobytes, default)
        data = self._ui.configlist(_tobytes(section), _tobytes(name),
                                   default=default)
        return pycompat.maplist(_tostr, data)

    def configStringItems(self, section):
        # type: (Text) -> List[Tuple[Text, Text]]
        """Returns a list of string (key, value) pairs under the specified
        section"""
        items = self._ui.configitems(_tobytes(section))
        return [(_tostr(k), _tostr(v)) for k, v in items]

    def hasConfig(self, section, name):
        # type: (Text, Text) -> bool
        return self._ui.hasconfig(_tobytes(section), _tobytes(name))


if pycompat.ispy3:
    _tostr = hglib.tounicode
    _tobytes = hglib.fromunicode
else:
    def _tostr(s):
        # keep ascii string as byte string on Python 2, which is supposedly
        # faster and safer.
        if encoding.isasciistr(s):
            return s
        return hglib.tounicode(s)

    def _tobytes(s):
        if not isinstance(s, pycompat.unicode):
            return s
        return hglib.fromunicode(s)
