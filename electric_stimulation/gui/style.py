# -*- coding: utf-8 -*-
"""Application stylesheet (scientific instrument look)."""

APP_STYLESHEET = """
QWidget {
    background-color: #1a1d23;
    color: #e8eaed;
    font-size: 13px;
}
QMainWindow, QDialog {
    background-color: #1a1d23;
}
QGroupBox {
    font-weight: 600;
    border: 1px solid #2e3440;
    border-radius: 6px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
    background-color: #21252b;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #9aa0a6;
}
QLabel {
    background: transparent;
    color: #e8eaed;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #0f1115;
    border: 1px solid #3c4450;
    border-radius: 4px;
    padding: 5px 8px;
    min-height: 22px;
    selection-background-color: #3d5a80;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #5b8def;
}
QComboBox::drop-down {
    border: none;
    width: 22px;
}
QCheckBox {
    spacing: 8px;
    background: transparent;
}
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3c4450;
    border-radius: 3px;
    background: #0f1115;
}
QCheckBox::indicator:checked {
    background: #5b8def;
    border-color: #5b8def;
}
QPushButton {
    border: none;
    border-radius: 5px;
    padding: 8px 16px;
    font-weight: 600;
    min-height: 28px;
}
QPushButton#btnStart {
    background-color: #2e7d4f;
    color: #ffffff;
}
QPushButton#btnStart:hover {
    background-color: #35965e;
}
QPushButton#btnStart:disabled {
    background-color: #2a3038;
    color: #6b7280;
}
QPushButton#btnStop {
    background-color: #a33b3b;
    color: #ffffff;
}
QPushButton#btnStop:hover {
    background-color: #c24a4a;
}
QPushButton#btnStop:disabled {
    background-color: #2a3038;
    color: #6b7280;
}
QPushButton#btnSecondary {
    background-color: #2a3038;
    color: #e8eaed;
    border: 1px solid #3c4450;
}
QPushButton#btnSecondary:hover {
    background-color: #343b46;
}
QFrame#statusPanel {
    background-color: #0f1115;
    border: 1px solid #2e3440;
    border-radius: 8px;
}
QLabel#statusPhase {
    font-size: 20px;
    font-weight: 700;
    background: transparent;
}
QLabel#statusCountdown {
    font-size: 14px;
    color: #9aa0a6;
    background: transparent;
}
QLabel#muted {
    color: #9aa0a6;
    font-size: 11px;
    background: transparent;
}
QStatusBar {
    background: #14171c;
    color: #9aa0a6;
    border-top: 1px solid #2e3440;
}
"""
