# libstempo

[![GitHub release (latest by date)](https://img.shields.io/github/v/release/vallis/libstempo)](https://github.com/vallis/libstempo/releases/latest)
[![PyPI](https://img.shields.io/pypi/v/libstempo)](https://pypi.org/project/libstempo/)
[![Conda Version](https://img.shields.io/conda/vn/conda-forge/libstempo.svg)](https://anaconda.org/conda-forge/libstempo)
[![libstempo CI tests](https://github.com/vallis/libstempo/actions/workflows/ci_tests.yml/badge.svg)](https://github.com/vallis/libstempo/actions/workflows/ci_tests.yml)


[![Python Versions](https://img.shields.io/badge/python-3.7%2C%203.8%2C%203.9%2C%203.10-blue.svg)]()
[![GitHub license](https://img.shields.io/github/license/Naereen/StrapDown.js.svg)](https://github.com/vallis/libstempo/blob/master/LICENSE)

`libstempo` is a Python wrapper around the [tempo2](https://bitbucket.org/psrsoft/tempo2/src/master/) pulsar timing package.


## Installation

### conda Install

`libstempo` is installed most simply via [conda](https://docs.conda.io/en/latest/) as the `tempo` dependency
is bundled in the conda recipe. Simply use
```bash
conda install -c conda-forge libstempo
```

### pip Install

To use `libstempo` with pip (or from source), tempo2 must be installed as a prerequisite. Currently there are two recommended methods to do this.

1. Install via script. 
    ```bash
    curl -sSL https://raw.githubusercontent.com/vallis/libstempo/master/install_tempo2.sh | sh
    ```
    This will install the tempo2 library in a local directory (`$HOME/.local`). This method is recommended if you do not need to use tempo2 directly but just need the installation for `libstempo`. You can also set the path to the install location. For example, to install in `/usr/local`, you could run:
    ```bash
    # need sudo if installing in a restricted location
    curl -sSL https://raw.githubusercontent.com/vallis/libstempo/master/install_tempo2.sh | sudo sh -s /usr/local
    ``` 
2. Install via the [instructions](https://bitbucket.org/psrsoft/tempo2/src/master/README.md) on the tempo2 homepage. If this method is used, the `TEMPO2` environment variable will need to be set to use `libstempo`.

In either case, it is best practice to set the `TEMPO2` environment
variable so that it can be easily discovered by `libstempo`.

The `libstempo` package can be installed via `pip`:
```bash
pip install libstempo
```

To use `astropy` for units:
```bash
pip install libstempo[astropy]
```

If you have installed `tempo2` in a location that is not in your path or not the default from `install_tempo2.sh`, you will need to install 
`libstempo` with an environment variable (e.g. if `tempo2` is in `/opt/local/bin`)
```bash
TEMPO2_PREFIX=/opt/local pip install libstempo
```
or
```bash
export TEMPO2_PREFIX=/opt/local
pip install libstempo
```

## Usage

See [Demo Notebook 1](https://github.com/vallis/libstempo/blob/master/demo/libstempo-demo.ipynb) for basic usage and [Demo Notebook 2](https://github.com/vallis/libstempo/blob/master/demo/libstempo-toasim-demo.ipynb) for simulation usage.

## Sandbox Mode (Crash-Protected)

libstempo includes a sandbox mode that provides crash isolation and automatic retry capabilities. This is particularly useful when working with problematic pulsars or long-running analyses where tempo2 crashes are common.

### Basic Usage

The sandbox provides a drop-in replacement for the standard `tempopulsar` class:

```python
from libstempo.sandbox import tempopulsar

# Basic usage - same API as regular tempopulsar
psr = tempopulsar(parfile="J1713.par", timfile="J1713.tim", dofit=False)
residuals = psr.residuals()
design_matrix = psr.designmatrix()
```

### Advanced Configuration

```python
from libstempo.sandbox import tempopulsar, Policy, configure_logging

# Configure logging for debugging
configure_logging(level="DEBUG", log_file="tempo2.log")

# Configure retry and timeout policies
policy = Policy(
    ctor_retry=5,           # Retry constructor 5 times on failure
    call_timeout_s=300.0,    # 5-minute timeout per RPC call
    max_calls_per_worker=1000,  # Recycle worker after 1000 calls
    max_age_s=3600,          # Recycle worker after 1 hour
    rss_soft_limit_mb=2048   # Recycle worker if memory exceeds 2GB
)

psr = tempopulsar(parfile="J1713.par", timfile="J1713.tim", policy=policy)
```

### Environment Support

The sandbox supports different Python environments:

```python
# Use virtual/conda environment
psr = tempopulsar(parfile="J1713.par", timfile="J1713.tim", env_name="tempo2_intel")

# Use system Python with Rosetta (macOS)
psr = tempopulsar(parfile="J1713.par", timfile="J1713.tim", env_name="arch")

# Use explicit Python path
psr = tempopulsar(parfile="J1713.par", timfile="J1713.tim", env_name="python:/path/to/python")
```

### Key Benefits

- **Crash Isolation**: Segfaults in tempo2 only kill the worker process, not your main kernel
- **Automatic Retry**: Built-in retry logic for transient failures
- **Worker Recycling**: Prevents memory leaks and resource accumulation
- **Environment Flexibility**: Support for conda, venv, and Rosetta environments
- **Enhanced Logging**: Comprehensive logging for debugging and monitoring
- **Proactive TOA Handling**: Automatically handles large TOA files to prevent "Too many TOAs" errors

### Performance

The sandbox adds ~9x initialization overhead but only ~1.2x overhead for computational operations like `residuals()` and `designmatrix()`. For heavy computations, the overhead becomes negligible relative to the actual work. Use sandbox when stability is critical, direct libstempo when performance is paramount.

### Bulk Loading

For processing many pulsars:

```python
from libstempo.sandbox import load_many, Policy

pairs = [("J1713.par", "J1713.tim"), ("J1909.par", "J1909.tim"), ...]
policy = Policy(ctor_retry=3, call_timeout_s=120.0)

ok_by_name, retried_by_name, failed_list = load_many(pairs, policy=policy, parallel=8)

print(f"Successfully loaded: {len(ok_by_name)}")
print(f"Required retries: {len(retried_by_name)}")
print(f"Failed: {len(failed_list)}")
```

### Error Handling

The sandbox defines specific exception types:

```python
from libstempo.sandbox import Tempo2Error, Tempo2Crashed, Tempo2Timeout

try:
    psr = tempopulsar(parfile="problematic.par", timfile="problematic.tim")
except Tempo2Crashed:
    print("Worker process crashed - likely a segfault")
except Tempo2Timeout:
    print("Worker timed out")
except Tempo2Error as e:
    print(f"Sandbox error: {e}")
```
