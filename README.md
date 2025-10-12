# Sonde Notifier

Get notified of incoming sondes using data from an AutoRX instance

## Installation

> [!NOTE]
> Currently only linux is being actively tested. Other operating systems might work,
> feel free to test it out on them.

### AutoRX setup

In radiosonde_auto_rx's station.cfg, payload_summary_enabled needs to be set to true.

While it's far from necessary, for optimal function ozi_update_rate should be set to zero.

### Software installation

```bash
# Start in whichever directory you want to install to

# Clone repository and enter
git clone https://github.com/DB8LE/sonde-notifier.git
cd sonde-notifier

# Create venv and enter it
python3 -m venv venv
source ./venv/bin/activate

# Install dependencies
# Note: optionally, systemctl journal support can be enabled by running
# `pip install .[journal]` instead. Journal support requires the dependency python3-systemd
pip install .


# Create config file based on example
cp config.example.toml config.toml

# Edit the config with your favourite editor
nano config.toml
```

### SystemD service

```bash
# Start in sonde-notifier install directory

# Copy provided systemd service
sudo cp ./sonde-notifier.service /etc/systemd/system/

# Replace all occurences of "<your_user>" with actual user
sudo sed -i "s/<your_user>/$(whoami)/g" /etc/systemd/system/sonde-notifier.service

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable sonde-notifier.service

# Start!
sudo systemctl start sonde-notifier.service
```
