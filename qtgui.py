# qtgui.py - PyQt4/5 compatibility wrapper
#
# Copyright 2015 Yuya Nishihara <yuya@tcha.org>
#
# This software may be used and distributed according to the terms of the
# GNU General Public License version 2 or any later version.

"""Thin compatibility wrapper for QtGui and QtWidgets of Qt5"""

from __future__ import absolute_import

from .qtcore import QT_API

if QT_API == 'PyQt5':
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import *
    QStyleOptionViewItemV2 = QStyleOptionViewItem
    QStyleOptionViewItemV3 = QStyleOptionViewItem
    QStyleOptionViewItemV4 = QStyleOptionViewItem
else:
    raise RuntimeError('unsupported Qt API: %s' % QT_API)
