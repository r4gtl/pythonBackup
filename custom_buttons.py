from PyQt5.QtWidgets import QPushButton, QToolBar, QAction, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt


def setup_toolbar(parent):
    tb = QToolBar("Tool Bar", parent)
    tb.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

    addSave = QAction(QIcon('icons/save.png'), "Salva", parent)
    addSave.triggered.connect(parent.addSave)
    tb.addAction(addSave)
    # addSave.triggered.connect(parent.func_add_save)

    deleteCmr = QAction(QIcon('icons/delete-folder.png'), "Elimina", parent)
    tb.addAction(deleteCmr)
    # deleteCmr.triggered.connect(parent.func_delete_cmr)

    exitAction = QAction(QIcon('icons/exit.png'), "Esci", parent)
    exitAction.triggered.connect(parent.close)
    # tb.addAction(exitAction)

    return tb