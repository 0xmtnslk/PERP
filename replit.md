# Cryptocurrency Auto-Trading System

## Overview

This is an automated cryptocurrency trading system that monitors Upbit exchange announcements for new coin listings and automatically executes futures trades on Bitget and Gate.io exchanges. The system uses web scraping to detect new coin announcements, converts symbol formats between exchanges, and places leveraged long positions when new USDT trading pairs are detected.

The system consists of multiple Python scripts working together: a web scraper for Upbit announcements, symbol format converters, trading bots for different exchanges, a Telegram bot for notifications, and a coordination system that manages all components.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Components
- **Web Scraping Module**: Monitors Upbit's announcement page for new coin listings using BeautifulSoup and requests
- **Symbol Format Conversion**: Converts coin symbols between different exchange formats (Upbit → Bitget/Gate.io)
- **Trading Engines**: Separate modules for Bitget and Gate.io that handle API authentication, leverage setting, and order placement
- **Telegram Bot Interface**: Provides user control and notifications through Telegram
- **IPC System**: Inter-process communication for coordinating between different system components
- **Main Coordinator**: Central orchestrator that manages all subsystems

### Trading Logic
- Continuously monitors new_coin_output.txt files for symbol changes
- When a new symbol is detected (different from initial_symbol), automatically triggers trading scripts
- Uses market orders with maximum available leverage
- Implements automatic profit-taking at configurable percentage gains
- Supports position closing and emergency stops

### Security Architecture
- API credentials managed through environment variables and encrypted JSON files
- Separate secret.json files for each exchange with API keys, trading amounts, and profit targets
- HMAC-SHA256 signature generation for secure API authentication
- Encryption utilities using Fernet symmetric encryption for sensitive data

### Data Storage
- SQLite database for user management and trading history (in Telegram bot)
- JSON files for configuration, order tracking, and symbol monitoring
- Text files for simple inter-process communication of current symbols
- Centralized notification configuration system

## External Dependencies

### Cryptocurrency Exchange APIs
- **Bitget API**: For futures trading, leverage setting, position management
- **Gate.io API**: Alternative futures trading platform with similar functionality
- **Upbit API**: For market data and new coin detection (read-only)

### Third-Party Libraries
- **python-telegram-bot**: Telegram bot interface and user interaction
- **requests**: HTTP client for API calls and web scraping
- **BeautifulSoup**: HTML parsing for Upbit announcement scraping
- **cryptography**: Encryption and security utilities for API key protection
- **websocket-client**: Real-time data streaming capabilities

### External Services
- **Telegram Bot API**: For user notifications and system control
- **Upbit Announcement Page**: Primary source for new coin listing detection

### Development Tools
- **sqlite3**: Embedded database for persistent storage
- **subprocess**: Process management for coordinating multiple scripts
- **threading**: Concurrent execution of monitoring and trading tasks