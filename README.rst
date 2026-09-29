====
scpi
====

Transport-independent, asyncio-based SCPI commands and device helpers for
Python 3.12, 3.13 and 3.14. Serial transport uses pyserial; VISA is not required.

Usage
-----

Install with ``pip install scpi`` or add the package with ``uv add scpi``.

* Instantiate a transport. GPIB devices use ``GPIBDeviceTransport``.
* Instantiate ``SCPIDevice`` with the transport, or with an explicit
  ``SCPIProtocol`` when you need to share a protocol.
* Await the device methods from your application's event loop.

For blocking scripts and interactive use, wrap a device with ``AIOWrapper``.
Each wrapper creates its own loop and closes it on ``quit()``. When wrappers
share a transport, pass ``loop=controller.loop`` to the device wrappers; only
that controller owns the loop. Quit device wrappers before their controller.
Calling ``quit()`` repeatedly is safe. Use the asynchronous API inside an
already running event loop.

For example, connect to an HP 6632B power supply::

    uv run --locked python examples/hp6632b_serial.py /dev/ttyUSB0

The example leaves an interactive ``dev`` object and registers shutdown with
``atexit``. See ``examples/`` for TCP and Prologix GPIB examples. Physical
instrument access and serial-port permissions are required for those examples.

Development
-----------

The project uses uv, Hatchling, Ruff, strict Pyrefly and prek::

    uv sync --locked
    uv run --locked prek install
    uv run --locked prek run --all-files
    uv run --locked pytest
    uv run --locked pyrefly check
    uv run --locked bandit -r src --skip B101

Run the supported Python matrix with ``uv run --locked tox``. Tox needs Python
3.12, 3.13 and 3.14 available; ``uv python install 3.12 3.13 3.14`` can install
them. Tests use fake devices and pyserial loopback ports and need no hardware.
The Bandit B101 exclusion permits existing internal assertions.

Release preparation
-------------------

From a clean working tree::

    uv run --locked bump-my-version bump patch
    uv lock
    uv run --locked prek run --all-files
    uv run --locked pytest
    uv build

The bump updates package metadata, the package version and its test. Commit
those files and ``uv.lock`` together. It does not automatically commit, tag,
publish or push. Builds retain ``LICENSE`` and ``py.typed`` and exclude the
local, untracked ``HANDOFF.md`` from source distributions.

Containers
----------

``Dockerfile`` uses Debian Trixie; ``Dockerfile_alpine`` uses Alpine 3.24.
Both use Python 3.14 and expose ``test``, ``tox``, ``devel_shell`` and
``production`` targets. Tox checks Python 3.12 through 3.14. Production installs
only runtime dependencies, non-editably, and prints the package version by
default. Pass a command to run your own script.

Build and run all targets locally::

    ./run_tests.sh
    CONTAINER_ENGINE=podman ./run_tests.sh

Filter a run or use an optional wheelhouse::

    CONTAINER_ENGINE=podman VARIANTS=alpine TARGETS=tox ./run_tests.sh
    WHEELHOUSE_URL=http://host.docker.internal:3141/debian/ VARIANTS=debian ./run_tests.sh

Sources are copied into images; no host virtualenv, SSH agent or source bind
mount is required. The wheelhouse is optional. To build a production image::

    docker build --target production -t scpi:local .
    docker run --rm scpi:local

Use ``podman`` in place of ``docker`` if preferred. Access to physical serial
instruments must be configured separately for your container engine.

CI
--

GitHub Actions runs checks on Python 3.12, 3.13 and 3.14, and builds/runs all
four container targets on both distributions. Container jobs use Docker.

TODO
----

Consider configurable carrier-detect and CTS checks for RS232 devices that
support those signals.
