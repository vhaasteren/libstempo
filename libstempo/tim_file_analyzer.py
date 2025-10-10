"""TimFileAnalyzer - Fast TIM file analyzer without PINT dependencies.

This module provides a lightweight class to quickly extract TOA MJD values
from TIM files using independent parsing logic that replicates PINT's functionality
without requiring PINT as a dependency. This is useful for environments where
PINT is not available or when you need a minimal implementation.

The implementation replicates the core functionality from PINT's toa.py module
for parsing TOA lines and handling TIM file commands.

Author: Rutger van Haasteren -- rutger@vhaasteren.com
Date:   2025-10-10
"""

import re
import logging
from pathlib import Path
from typing import List, Set, Dict, Tuple, Optional

logger = logging.getLogger(__name__)


# TOA commands that can appear in TIM files
TOA_COMMANDS = (
    "DITHER",
    "EFAC",
    "EMAX",
    "EMAP",
    "EMIN",
    "EQUAD",
    "FMAX",
    "FMIN",
    "INCLUDE",
    "INFO",
    "JUMP",
    "MODE",
    "NOSKIP",
    "PHA1",
    "PHA2",
    "PHASE",
    "SEARCH",
    "SIGMA",
    "SIM",
    "SKIP",
    "TIME",
    "TRACK",
    "ZAWGT",
    "FORMAT",
    "END",
)

# Simple observatory name mapping (subset of PINT's observatory registry)
# This covers the most common observatories used in TOA files
OBSERVATORY_NAMES = {
    # Common single-letter codes
    "A": "Arecibo",
    "AO": "Arecibo",
    "ARECIBO": "Arecibo",
    "B": "GBT",
    "GBT": "GBT",
    "GREEN_BANK": "GBT",
    "C": "CHIME",
    "CHIME": "CHIME",
    "D": "DSS-43",
    "E": "Effelsberg",
    "EFFELSBERG": "Effelsberg",
    "F": "FAST",
    "FAST": "FAST",
    "G": "GMRT",
    "GMRT": "GMRT",
    "H": "Hobart",
    "HOBART": "Hobart",
    "I": "IAR",
    "IAR": "IAR",
    "J": "Jodrell",
    "JB": "Jodrell",
    "JODRELL": "Jodrell",
    "K": "Kalyazin",
    "KALYAZIN": "Kalyazin",
    "L": "Lovell",
    "LOVELL": "Lovell",
    "M": "MeerKAT",
    "MEERKAT": "MeerKAT",
    "N": "Nancay",
    "NANCAY": "Nancay",
    "O": "Ooty",
    "OOTY": "Ooty",
    "P": "Parkes",
    "PARKES": "Parkes",
    "Q": "Qitai",
    "QITAI": "Qitai",
    "R": "RATAN",
    "RATAN": "RATAN",
    "S": "Sardinia",
    "SARDINIA": "Sardinia",
    "T": "Tianma",
    "TIANMA": "Tianma",
    "U": "URUMQI",
    "URUMQI": "URUMQI",
    "V": "VLA",
    "VLA": "VLA",
    "W": "Westerbork",
    "WESTERBORK": "Westerbork",
    "X": "Xinjiang",
    "XINJIANG": "Xinjiang",
    "Y": "Yunnan",
    "YUNNAN": "Yunnan",
    "Z": "Zelenchukskaya",
    "ZELENCHUKSKAYA": "Zelenchukskaya",
    # Special codes
    "@": "Barycenter",
    "BARYCENTER": "Barycenter",
    "SSB": "Barycenter",
    # Spacecraft observatories
    "FERMI": "Fermi",
    "NICER": "NICER",
    "SWIFT": "Swift",
    "RXTE": "RXTE",
    "XTE": "RXTE",
}


def _toa_format(line: str, fmt: str = "Unknown") -> str:
    """Determine the type of a TOA line.
    
    Identifies a TOA line as one of the following types:
    Comment, Command, Blank, Tempo2, Princeton, ITOA, Parkes, Unknown.
    
    This replicates PINT's _toa_format function.
    """
    # Check for comments first
    if (
        line.startswith("C ") and len(line) > 2 and not line[2].isdigit()  # C followed by non-digit
        or line.startswith("c ") and len(line) > 2 and not line[2].isdigit()  # c followed by non-digit
        or line.startswith("#")
        or line.startswith("CC ")
    ):
        return "Comment"
    
    # Check for commands
    if line.upper().lstrip().startswith(TOA_COMMANDS):
        return "Command"
    
    # Check for blank lines
    if re.match(r"^\s*$", line):
        return "Blank"
    
    # Check for Princeton format: starts with single observatory code followed by space
    if re.match(r"[0-9a-zA-Z@] ", line):
        return "Princeton"
    
    # Check for Tempo2 format: long lines, explicitly marked as Tempo2, or structured like Tempo2
    if len(line) > 80 or fmt == "Tempo2":
        return "Tempo2"
    
    # Additional Tempo2 detection: if it looks like a Tempo2 TOA line (has 5+ space-separated fields)
    fields = line.split()
    if len(fields) >= 5:
        # Check if it looks like a Tempo2 TOA line: name freq mjd error obs [flags...]
        try:
            # Try to parse as Tempo2: name freq mjd error obs
            float(fields[1])  # frequency should be numeric
            float(fields[2])  # MJD should be numeric  
            float(fields[3])  # error should be numeric
            # If we get here, it looks like Tempo2 format
            return "Tempo2"
        except (ValueError, IndexError):
            pass
    
    # Check for Parkes format: starts with space, has decimal at position 42
    if re.match(r"^ ", line) and len(line) > 41 and line[41] == ".":
        return "Parkes"
    
    # Check for ITOA format: two non-space chars, decimal at position 15
    if re.match(r"\S\S", line) and len(line) > 14 and line[14] == ".":
        return "ITOA"
    
    # Default to Unknown
    return "Unknown"


def _get_observatory_name(obs_code: str) -> str:
    """Get observatory name from observatory code.
    
    This is a simplified version of PINT's get_observatory function
    that only handles the most common observatory codes.
    
    Args:
        obs_code: Observatory code (e.g., 'A', 'AO', '@')
        
    Returns:
        Observatory name
    """
    obs_code_upper = obs_code.upper()
    return OBSERVATORY_NAMES.get(obs_code_upper, obs_code_upper)


def _parse_TOA_line(line: str, fmt: str = "Unknown") -> Tuple[Optional[Tuple[int, float]], dict]:
    """Parse a one-line ASCII time-of-arrival.
    
    Return an MJD tuple and a dictionary of other TOA information.
    The format can be one of: Comment, Command, Blank, Tempo2,
    Princeton, ITOA, Parkes, or Unknown.
    
    This replicates PINT's _parse_TOA_line function.
    """
    MJD = None
    fmt = _toa_format(line, fmt)
    d = dict(format=fmt)
    
    if fmt == "Princeton":
        # Princeton format
        # ----------------
        # columns  item
        # 1-1     Observatory (one-character code) '@' is barycenter
        # 2-2     must be blank
        # 16-24   Observing frequency (MHz)
        # 25-44   TOA (decimal point must be in column 30 or column 31)
        # 45-53   TOA uncertainty (microseconds)
        # 69-78   DM correction (pc cm^-3)
        try:
            # Handle both fixed-width and space-separated Princeton format
            if len(line) >= 78:  # Fixed-width format
                d["obs"] = _get_observatory_name(line[0].upper())
                d["freq"] = float(line[15:24])
                d["error"] = float(line[44:53])
                ii, ff = line[24:44].split(".")
                ii = int(ii)
                # For very old TOAs, see https://tempo.sourceforge.net/ref_man_sections/toa.txt
                if ii < 40000:
                    ii += 39126
                MJD = (ii, float(f"0.{ff}"))
                try:
                    d["ddm"] = str(float(line[68:78]))
                except ValueError:
                    d["ddm"] = str(0.0)
            else:  # Space-separated format (fallback)
                fields = line.split()
                if len(fields) >= 4:
                    d["obs"] = _get_observatory_name(fields[0].upper())
                    d["freq"] = float(fields[1])
                    d["error"] = float(fields[3])
                    # Parse MJD
                    if "." in fields[2]:
                        ii, ff = fields[2].split(".")
                        ii = int(ii)
                        if ii < 40000:
                            ii += 39126
                        MJD = (ii, float(f"0.{ff}"))
                    else:
                        ii = int(fields[2])
                        if ii < 40000:
                            ii += 39126
                        MJD = (ii, 0.0)
                    d["ddm"] = str(0.0)  # Default DM correction
                else:
                    raise ValueError("Not enough fields for Princeton format")
        except (ValueError, IndexError) as e:
            # If parsing fails, treat as unknown format
            logger.debug(f"Failed to parse Princeton format line: {e}")
            d["format"] = "Unknown"
            
    elif fmt == "Tempo2":
        # This could use more error catching...
        try:
            fields = line.split()
            d["name"] = fields[0]
            d["freq"] = float(fields[1])
            if "." in fields[2]:
                ii, ff = fields[2].split(".")
                MJD = (int(ii), float(f"0.{ff}"))
            else:
                MJD = (int(fields[2]), 0.0)
            d["error"] = float(fields[3])
            d["obs"] = _get_observatory_name(fields[4].upper())
            # All the rest should be flags
            flags = fields[5:]
            
            # Flags and flag-values should be given in pairs.
            # The for loop below will fail otherwise.
            if len(flags) % 2 != 0:
                raise ValueError(
                    f"Flags and flag-values should be given in pairs. The given flags are {' '.join(flags)}"
                )
            
            for i in range(0, len(flags), 2):
                k, v = flags[i].lstrip("-"), flags[i + 1]
                if k in ["error", "freq", "scale", "MJD", "flags", "obs", "name"]:
                    raise ValueError(f"TOA flag ({k}) will overwrite TOA parameter!")
                if not k:
                    raise ValueError(f"The string {repr(flags[i])} is not a valid flag")
                d[k] = v
        except (ValueError, IndexError) as e:
            # If parsing fails, treat as unknown format
            logger.debug(f"Failed to parse Tempo2 format line: {e}")
            d["format"] = "Unknown"
            
    elif fmt == "Command":
        d[fmt] = line.split()
    elif fmt == "Parkes":
        """
        columns     item
        1-1         Must be blank
        26-34       Observing Frequency (MHz)
        35-55       TOA (decimal point must be in column 42)
        56-63       Phase offset (fraction of P0, added to TOA)
        64-71       TOA uncertainty
        80-80       Observatory (1 character)
        """
        try:
            d["name"] = line[1:25]
            d["freq"] = float(line[25:34])
            ii = line[34:41]
            ff = line[42:55]
            MJD = int(ii), float(f"0.{ff}")
            phaseoffset = float(line[55:62])
            if phaseoffset != 0:
                raise ValueError(
                    f"Cannot interpret Parkes format with phaseoffset={phaseoffset} yet"
                )
            d["error"] = float(line[63:71])
            d["obs"] = _get_observatory_name(line[79].upper())
        except (ValueError, IndexError) as e:
            # If parsing fails, treat as unknown format
            logger.debug(f"Failed to parse Parkes format line: {e}")
            d["format"] = "Unknown"
            
    elif fmt == "ITOA":
        raise RuntimeError(f"TOA format '{fmt}' not implemented yet")
    elif fmt not in ["Blank", "Comment"]:
        raise RuntimeError(
            f"Unable to identify TOA format for line {line!r}, expecting {fmt}"
        )
    return MJD, d


class TimFileAnalyzer:
    """Fast TIM file analyzer for timespan calculation without PINT dependencies.

    This class efficiently extracts TOA MJD values from TIM files using
    independent parsing logic that replicates PINT's functionality,
    providing both performance and robustness for timespan calculations.
    
    The analyzer caches results per file to avoid duplicate parsing when both
    timespan and TOA count are needed for the same file.
    """

    def __init__(self):
        """Initialize the TIM file analyzer."""
        self.logger = logger
        self._processed_files: Set[Path] = set()
        # Cache for storing timespan and TOA counts per file (not MJD values to save memory)
        self._file_cache: Dict[Path, Tuple[float, int]] = {}

    def _get_timespan_and_count(self, tim_file_path: Path) -> Tuple[float, int]:
        """Get timespan and TOA count from TIM file, using cache if available.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            Tuple of (timespan_in_days, toa_count)
        """
        # Check cache first
        if tim_file_path in self._file_cache:
            self.logger.debug(f"Using cached data for {tim_file_path}")
            return self._file_cache[tim_file_path]

        try:
            self._processed_files.clear()
            mjd_values = self._extract_mjd_values_recursive(tim_file_path)
            toa_count = len(mjd_values)

            if toa_count == 0:
                timespan = 0.0
            else:
                # Calculate timespan as max - min (no need to sort)
                timespan = float(max(mjd_values) - min(mjd_values))

            # Cache only the results we need (timespan and count)
            self._file_cache[tim_file_path] = (timespan, toa_count)

            if toa_count > 0:
                self.logger.debug(
                    f"Cached data for {tim_file_path}: {timespan:.1f} days, {toa_count} TOAs"
                )
            else:
                self.logger.debug(f"Cached data for {tim_file_path}: No TOAs found")
            return timespan, toa_count

        except Exception as e:
            self.logger.warning(f"Parsing failed for {tim_file_path}: {e}")
            self.logger.debug(
                "File may contain non-standard TIM format or malformed data"
            )
            # Cache empty result to avoid repeated failures
            empty_result = (0.0, 0)
            self._file_cache[tim_file_path] = empty_result
            return empty_result

    def calculate_timespan(self, tim_file_path: Path) -> float:
        """Calculate timespan from TIM file using independent parsing logic.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            Timespan in days (max(mjd) - min(mjd))
        """
        timespan, toa_count = self._get_timespan_and_count(tim_file_path)

        if toa_count == 0:
            self.logger.warning(f"No TOAs found in {tim_file_path}")
            return 0.0

        self.logger.debug(
            f"Timespan for {tim_file_path}: {timespan:.1f} days ({toa_count} TOAs)"
        )
        return timespan

    def count_toas(self, tim_file_path: Path) -> int:
        """Count the number of TOAs in a TIM file.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            Number of TOAs found in the file
        """
        _, toa_count = self._get_timespan_and_count(tim_file_path)

        self.logger.debug(
            f"TOA count for {tim_file_path}: {toa_count} TOAs"
        )
        return toa_count

    def clear_cache(self) -> None:
        """Clear the file cache."""
        self._file_cache.clear()
        self.logger.debug("File cache cleared")

    def get_timespan_and_count(self, tim_file_path: Path) -> Tuple[float, int]:
        """Get both timespan and TOA count efficiently using cached data.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            Tuple of (timespan_in_days, toa_count)
        """
        timespan, toa_count = self._get_timespan_and_count(tim_file_path)

        if toa_count == 0:
            self.logger.warning(f"No TOAs found in {tim_file_path}")
            return 0.0, 0

        self.logger.debug(
            f"Timespan and count for {tim_file_path}: {timespan:.1f} days, {toa_count} TOAs"
        )
        return timespan, toa_count

    def _extract_mjd_values_recursive(self, tim_file_path: Path) -> List[float]:
        """Recursively extract MJD values from TIM file and included files.

        Args:
            tim_file_path: Path to the TIM file

        Returns:
            List of MJD values from all TOA lines
        """
        mjd_values = []

        # Avoid infinite recursion
        if tim_file_path in self._processed_files:
            self.logger.warning(f"Circular INCLUDE detected: {tim_file_path}")
            return mjd_values

        self._processed_files.add(tim_file_path)

        try:
            with open(tim_file_path, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Skip empty lines
                    if not line:
                        continue

                    # Use independent parsing for both TOA lines and commands
                    try:
                        mjd_tuple, d = _parse_TOA_line(line)
                    except Exception as e:
                        # Parsing may fail on malformed lines - skip them gracefully
                        self.logger.debug(
                            f"Skipping malformed line in {tim_file_path}: {line.strip()} - {e}"
                        )
                        continue

                    # Handle commands (especially INCLUDE)
                    if d["format"] == "Command":
                        self._handle_command(d, tim_file_path, mjd_values)
                        continue

                    # Skip non-TOA lines
                    if d["format"] in ("Comment", "Blank", "Unknown"):
                        continue

                    # Extract MJD from TOA line
                    if mjd_tuple is not None:
                        # Convert (int, float) tuple to float MJD
                        mjd_value = float(mjd_tuple[0]) + float(mjd_tuple[1])
                        mjd_values.append(mjd_value)

        except Exception as e:
            self.logger.error(f"Error reading TIM file {tim_file_path}: {e}")

        return mjd_values

    def _handle_command(
        self, d: dict, current_file: Path, mjd_values: List[float]
    ) -> None:
        """Handle TIM file commands using parsed command data.

        Args:
            d: Parsed command dictionary
            current_file: Current TIM file being processed
            mjd_values: List to extend with MJD values from included files
        """
        if d["format"] != "Command":
            return

        cmd = d["Command"][0].upper()

        if cmd == "INCLUDE":
            if len(d["Command"]) < 2:
                self.logger.warning(f"INCLUDE command without filename: {d['Command']}")
                return

            include_file = d["Command"][1]
            include_path = current_file.parent / include_file

            if include_path.exists():
                self.logger.debug(f"Processing included TOA file {include_path}")
                included_mjds = self._extract_mjd_values_recursive(include_path)
                mjd_values.extend(included_mjds)
            else:
                self.logger.warning(f"INCLUDE file not found: {include_path}")
        # Other commands don't affect timespan calculation
