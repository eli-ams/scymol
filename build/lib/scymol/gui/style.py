STYLE = r"""
QWidget {
    color: #172528;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 10pt;
}
QMainWindow { background: #f4f8f8; }
QFrame#header { background: #285f66; border-bottom: 1px solid #1d4b51; }
QLabel#brand { color: white; font-size: 16pt; font-weight: 700; }
QLabel#projectPath { color: #d2e8ea; }
QLabel#pageTitle { font-size: 20pt; font-weight: 650; color: #285f66; }
QLabel#pageDescription { color: #526a6d; font-size: 10.5pt; }
QLabel#sectionTitle { font-size: 11pt; font-weight: 650; color: #376d74; }
QLabel#activeToolStatus {
    background: #dceff0; color: #285f66; border: 1px solid #9bc6ca;
    border-radius: 10px; padding: 4px 10px; font-weight: 600;
}
QLabel#tutorialProgress {
    color: #4b8a92; font-size: 9pt; font-weight: 700;
}
QDialog#tutorialWindow {
    background: #f4f8f8; border: 2px solid #4b8a92;
}
QWidget[tutorialTarget="true"] {
    border: 3px solid #4b8a92;
}
QLabel#inlineValidation[state="failed"] {
    background: #f9dddd; color: #8a2929; border: 1px solid #e9b9b9;
    border-radius: 5px; padding: 6px;
}
QLabel#note {
    background: #edf6f7; border: 1px solid #c9dfe2; border-radius: 6px;
    padding: 9px; color: #42666b;
}
QLabel#stageStatus {
    background: #e6eae9; border-radius: 11px; padding: 4px 10px; font-weight: 600;
}
QLabel#stageStatus[state="complete"] { background: #d9ecee; color: #2d6f76; }
QLabel#stageStatus[state="running"] { background: #fff0c7; color: #785b05; }
QLabel#stageStatus[state="failed"] { background: #f9dddd; color: #8a2929; }
QLabel#stageStatus[state="pending"] { background: #e6ebec; color: #526467; }
QPushButton {
    background: #ffffff; border: 1px solid #c9d6d8; border-radius: 6px; padding: 6px 11px;
}
QPushButton:hover { border-color: #78adb2; background: #f7fbfb; }
QPushButton:disabled { color: #93a1a3; background: #edf1f1; }
QPushButton#primaryButton {
    color: white; background: #4b8a92; border-color: #4b8a92;
    padding: 8px 18px; font-weight: 650;
}
QPushButton#primaryButton:hover { background: #3d777f; }
QPushButton#startupChoiceButton {
    color: #285f66; background: #ffffff; border: 2px solid #9bc6ca;
    border-radius: 10px; padding: 18px; font-size: 11pt; font-weight: 650;
}
QPushButton#startupChoiceButton:hover {
    background: #edf6f7; border-color: #4b8a92;
}
QPushButton#viewModeButton { border-radius: 0; margin-left: -1px; min-width: 52px; }
QPushButton#viewModeButton:checked {
    color: white; background: #4b8a92; border-color: #4b8a92; font-weight: 650;
}
QPushButton#dangerButton { color: #9a3434; }
QProgressBar::chunk { background: #4b8a92; }
QGroupBox {
    background: white; border: 1px solid #d8e1e2; border-radius: 8px;
    margin-top: 12px; padding: 12px; font-weight: 650;
}
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QListWidget, QTableWidget, QPlainTextEdit {
    background: white; border: 1px solid #c9d8da; border-radius: 5px;
    padding: 5px; selection-background-color: #86bac0;
}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled,
QComboBox:disabled, QListWidget:disabled, QTableWidget:disabled,
QPlainTextEdit:disabled {
    color: #8b9698; background: #e6ebeb; border-color: #d2d9da;
}
QCheckBox:disabled, QRadioButton:disabled, QLabel:disabled {
    color: #929c9e;
}
QGroupBox:disabled {
    color: #8f999b; background: #eef1f1; border-color: #d9dede;
}
QLineEdit[invalid="true"], QSpinBox[invalid="true"], QDoubleSpinBox[invalid="true"] {
    border: 1px solid #c55a5a; background: #fff7f7;
}
QTableWidget { alternate-background-color: #f3f7f7; gridline-color: #d9e2e3; }
QTableWidget::item:selected { background-color: #d9ecee; color: #285f66; }
QHeaderView::section {
    background-color: #edf3f4; color: #376d74; border: 0;
    border-right: 1px solid #d5dfe1; border-bottom: 1px solid #cad7d9;
    padding: 6px; font-weight: 600;
}
QTabWidget::pane { background: #fbfcfc; border: 1px solid #d8e1e2; }
QTabBar::tab { background: #e8eeee; padding: 10px 16px; margin-right: 2px; }
QTabBar::tab:selected { background: #fbfcfc; color: #327780; font-weight: 650; }
QTabBar::tab:disabled { color: #8b999b; }
QFrame#runBar { background: white; border-top: 1px solid #d8e1e2; }
QFrame#sidePanel { background: #f7fafa; border: 1px solid #d8e1e2; border-radius: 7px; }
QFrame#sourceBar {
    background: #edf6f7; border: 1px solid #c9dfe2; border-radius: 7px;
}
QFrame#sourceChoiceCard {
    background: white; border: 1px solid #c9dfe2; border-radius: 9px;
}
QPushButton#sourceChoiceButton {
    color: #327780; background: #edf6f7; border-color: #78adb2; font-weight: 650;
}
QPushButton#sourceChoiceButton:checked {
    color: white; background: #4b8a92; border-color: #376d74; font-weight: 650;
}
QGraphicsView { border: 1px solid #cad7d9; border-radius: 7px; background: #27383b; }
QPlainTextEdit#scriptPreview, QPlainTextEdit#console {
    background: #152427; color: #d6e6e8; border: 0;
    font-family: "Cascadia Mono", "Consolas", monospace; font-size: 9pt;
}
QSplitter::handle { background: #d9e3e4; width: 4px; }
QPushButton#primaryButton:disabled, QPushButton#sourceChoiceButton:disabled,
QPushButton#startupChoiceButton:disabled, QPushButton#dangerButton:disabled {
    color: #95a0a1; background: #e4e9e9; border-color: #d3dada;
}
"""
