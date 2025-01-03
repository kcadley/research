# Custom Trading APIs

## About
---
 This is a Python-based library designed to provide trade execution interfaces, market data retrieval, and derivatives modeling capabilities. The APIs support seamless integration with specific brokers and data providers, with a focus on flexibility for the user. Each module is comprehensively documented, allowing for easy help() queries and providing detailed inline comments.

This project is particularly valuable for traders working with a variety of derivatives or currency spot markets who hold accounts with Oanda and TastyTrade. However, even if you use different services, the module implementations may still provide useful insights for your custom development needs. Your constructive feedback is always welcome—especially ideas for module expansion. Happy trading.



## Modules
---
- **dxlink** - Retrieves live & historic market data from CME
- **fastoanda** - Supports trade execution against Oanda brokerage accounts. This is a streamlined version of my PyPi release (https://pypi.org/project/easyoanda/), which might be worth checking out in tandum - the PyPi link provides a full how-to guide for the module and couple of tips/tricks on production ready execution
- **markethours** - Evaluates global market hours, determines unknown options and futures settlement / expirations dates
- **oalink** - Retrieves live & historic market data for FX currencies (spot)
- **tsty** - Supports account management against TastyTrade brokerage accounts, with trade execution supported via custom payloads requests 

