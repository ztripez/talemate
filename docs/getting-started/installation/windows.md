## Quick install instructions

1. Download the latest Talemate release ZIP from the [Releases page](https://github.com/vegu-ai/talemate/releases) and extract it anywhere on your system (for example, `C:\Talemate`).
2. Double-click **`start.bat`**.
   - On the very first run Talemate will automatically:
     1. Download a portable build of Python 3 and Node.js (no global installs required).
     2. Create and configure a Python virtual environment.
     3. Install all back-end and front-end dependencies with the included *uv* and *npm*.
     4. Build the web client.
3. When the console window prints **"Talemate is now running"** and the logo appears, open your browser at **http://localhost:8080**.

!!! note "First start can take a while"
    The initial download and dependency installation may take several minutes, especially on slow internet connections. The console will keep you updated – just wait until the Talemate logo shows up.

### Optional: CUDA support

If you have an NVIDIA GPU and want CUDA acceleration for larger embedding models:

1. Close Talemate (if it is running).
2. Double-click **`install-cuda.bat`**. This script swaps the CPU-only Torch build for the CUDA 12.8 build.
3. Start Talemate again via **`start.bat`**.

## Maintenance & advanced usage

| Script | Purpose |
|--------|---------|
| **`start.bat`** | Primary entry point – performs the initial install if needed and then starts Talemate. |
| **`install.bat`** | Runs the installer without launching the server. Useful for automated setups or debugging. |
| **`install-cuda.bat`** | Installs the CUDA-enabled Torch build (run after the regular install). |
| **`update.bat`** | Pulls the latest changes from GitHub, updates dependencies, rebuilds the web client. |

<<<<<<< HEAD
### How to Install npm

1. Download Node.js from the official site [https://nodejs.org/en/download/prebuilt-installer](https://nodejs.org/en/download/prebuilt-installer).
2. Run the installer (the .msi installer is recommended).
3. Follow the prompts in the installer (Accept the license agreement, click the NEXT button a bunch of times and accept the default installation settings).

### Usage of the Supplied bat Files

#### install.bat

This batch file is used to set up the project on your local machine. It creates a virtual environment using uv and installs dependencies. It then navigates to the frontend directory and installs the necessary npm packages.

To run this file, simply double click on it or open a command prompt in the same directory and type `install.bat`.

#### update.bat

If you are inside a git checkout of talemate you can use this to pull and reinstall talemate if there have been updates.

!!! note "CUDA needs to be reinstalled manually"
    Running `update.bat` will downgrade your torch install to the non-CUDA version, so if you want CUDA support you will need to run the `install-cuda.bat` script after the update is finished.

#### start.bat

This batch file is used to start the backend and frontend servers.

To run this file, simply double click on it or open a command prompt in the same directory and type `start.bat`.
=======
No system-wide Python or Node.js is required – Talemate uses the embedded runtimes it downloads automatically.
>>>>>>> upstream/prep-0.31.0
