from PyQt5.QtCore import QRegExp
from PyQt5.QtGui import QColor, QTextCharFormat, QFont, QSyntaxHighlighter
from typing import Optional
from logging_functions import print_to_log, log_function_call


class LammpsSyntaxHighlighter(QSyntaxHighlighter):
    @log_function_call
    def __init__(self, parent: Optional[QSyntaxHighlighter] = None) -> None:
        """
        Initialize the LAMMPS syntax highlighter with specific highlighting rules.

        :param parent: The parent editor or document where the highlighter will be applied.
        :return: None
        :rtype: None
        """

        super(LammpsSyntaxHighlighter, self).__init__(parent)

        # Initialize the list of highlighting rules
        self.highlightingRules = []

        # Keyword format
        keywordFormat = QTextCharFormat()
        keywordFormat.setForeground(QColor("blue"))
        keywordFormat.setFontWeight(QFont.Bold)

        # Keywords
        keywords = [
            "read_data",
            "read_restart",
            "pair_style",
            "pair_coeff",
            "bond_style",
            "angle_style",
            "dihedral_style",
            "improper_style",
            "fix",
            "unfix",
            "minimize",
            "thermo_style",
            "thermo_modify",
            "dump",
            "restart",
            "run",
            "velocity",
            "region",
            "group",
            "timestep",
            "neighbor",
            "neigh_modify",
            "compute",
            "variable",
            "units",
            "atom_style",
            "boundary",
            "lattice",
            "create_atoms",
            "special_bonds",
            "pair_modify",
            "reset_timestep",
            "min_style",
            "min_modify",
            "thermo",
            "undump",
            "reset_timestep",
            "all",
            "npt",
            "nvt",
            "nve",
            "nph",
            "custom",
        ]

        # Pattern for keywords
        for keyword in keywords:
            pattern = QRegExp("\\b" + keyword + "\\b")
            self.highlightingRules.append((pattern, keywordFormat))

        # Bracket format
        bracketFormat = QTextCharFormat()
        bracketFormat.setFontWeight(QFont.Bold)

        # Patterns for brackets
        brackets = ["\\(", "\\)", "\\[", "\\]", "\\{", "\\}"]

        # Rule for brackets
        for bracket in brackets:
            pattern = QRegExp(bracket)
            self.highlightingRules.append((pattern, bracketFormat))

    def highlightBlock(self, text: str) -> None:
        """
        Apply syntax highlighting to the given block of text.

        This method is called automatically by the QSyntaxHighlighter to apply the highlighting rules
        to each block of text in the document.

        :param text: The text of the current block to be highlighted.
        :return: None
        :rtype: None
        """

        # Apply the highlighting rules to the current block of text
        for pattern, format in self.highlightingRules:
            expression = QRegExp(pattern)
            index = expression.indexIn(text)
            while index >= 0:
                length = expression.matchedLength()
                self.setFormat(index, length, format)
                index = expression.indexIn(text, index + length)

        # Continue with the rest of the text block
        self.setCurrentBlockState(0)
