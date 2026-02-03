"""
Stealth Browser - Anti-detection measures for web automation

Features:
- Canvas fingerprint randomization
- WebGL vendor/renderer spoofing
- AudioContext fingerprint masking
- Navigator property spoofing
- WebRTC leak prevention
- Timezone/language spoofing
"""
from __future__ import annotations

import random
import hashlib
from dataclasses import dataclass, field
from typing import Any, Optional
from loguru import logger


@dataclass
class StealthConfig:
    """Configuration for stealth features"""
    # Canvas
    canvas_noise: bool = True
    canvas_noise_level: float = 0.1  # 0-1

    # WebGL
    webgl_spoof: bool = True
    webgl_vendor: Optional[str] = None  # Auto-generate if None
    webgl_renderer: Optional[str] = None

    # Audio
    audio_noise: bool = True
    audio_noise_level: float = 0.0001

    # Navigator
    navigator_spoof: bool = True
    platform: Optional[str] = None
    hardware_concurrency: Optional[int] = None
    device_memory: Optional[int] = None

    # WebRTC
    webrtc_block: bool = True

    # Timezone/Language
    timezone: Optional[str] = None
    language: str = "en-US"
    languages: list[str] = field(default_factory=lambda: ["en-US", "en"])

    # Plugins
    plugins_spoof: bool = True


# Common WebGL vendors and renderers for spoofing
WEBGL_CONFIGS = [
    {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA GeForce GTX 1080 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0)"},
    {"vendor": "Intel Inc.", "renderer": "Intel Iris OpenGL Engine"},
    {"vendor": "Apple Inc.", "renderer": "Apple M1"},
    {"vendor": "NVIDIA Corporation", "renderer": "GeForce GTX 1660 Ti/PCIe/SSE2"},
]

# Common platforms
PLATFORMS = [
    "Win32",
    "MacIntel",
    "Linux x86_64",
]

# Timezones
TIMEZONES = [
    "America/New_York",
    "America/Los_Angeles",
    "America/Chicago",
    "Europe/London",
    "Europe/Paris",
    "Asia/Tokyo",
]


def generate_stealth_scripts(config: StealthConfig, seed: Optional[str] = None) -> str:
    """
    Generate JavaScript for stealth browser injection.

    Args:
        config: Stealth configuration
        seed: Optional seed for deterministic randomization

    Returns:
        JavaScript code to inject
    """
    if seed:
        random.seed(hashlib.md5(seed.encode()).hexdigest())

    scripts = []

    # Canvas fingerprint noise
    if config.canvas_noise:
        scripts.append(_canvas_noise_script(config.canvas_noise_level))

    # WebGL spoofing
    if config.webgl_spoof:
        webgl_config = _select_webgl_config(config)
        scripts.append(_webgl_spoof_script(webgl_config))

    # Audio fingerprint noise
    if config.audio_noise:
        scripts.append(_audio_noise_script(config.audio_noise_level))

    # Navigator spoofing
    if config.navigator_spoof:
        scripts.append(_navigator_spoof_script(config))

    # WebRTC blocking
    if config.webrtc_block:
        scripts.append(_webrtc_block_script())

    # Timezone spoofing
    if config.timezone:
        scripts.append(_timezone_spoof_script(config.timezone))

    # Plugin spoofing
    if config.plugins_spoof:
        scripts.append(_plugins_spoof_script())

    # Reset random seed
    if seed:
        random.seed()

    return "\n\n".join(scripts)


def _canvas_noise_script(noise_level: float) -> str:
    """Generate canvas noise injection script"""
    return f"""
// Canvas Fingerprint Noise
(function() {{
    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function(x, y, w, h) {{
        const imageData = originalGetImageData.call(this, x, y, w, h);
        const data = imageData.data;
        const noise = {noise_level};

        for (let i = 0; i < data.length; i += 4) {{
            // Add small random noise to RGB channels
            data[i] = Math.max(0, Math.min(255, data[i] + Math.floor((Math.random() - 0.5) * noise * 255)));
            data[i + 1] = Math.max(0, Math.min(255, data[i + 1] + Math.floor((Math.random() - 0.5) * noise * 255)));
            data[i + 2] = Math.max(0, Math.min(255, data[i + 2] + Math.floor((Math.random() - 0.5) * noise * 255)));
        }}

        return imageData;
    }};

    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type, quality) {{
        const ctx = this.getContext('2d');
        if (ctx) {{
            const imageData = ctx.getImageData(0, 0, this.width, this.height);
            ctx.putImageData(imageData, 0, 0);
        }}
        return originalToDataURL.call(this, type, quality);
    }};

    const originalToBlob = HTMLCanvasElement.prototype.toBlob;
    HTMLCanvasElement.prototype.toBlob = function(callback, type, quality) {{
        const ctx = this.getContext('2d');
        if (ctx) {{
            const imageData = ctx.getImageData(0, 0, this.width, this.height);
            ctx.putImageData(imageData, 0, 0);
        }}
        return originalToBlob.call(this, callback, type, quality);
    }};
}})();
"""


def _select_webgl_config(config: StealthConfig) -> dict:
    """Select WebGL vendor/renderer"""
    if config.webgl_vendor and config.webgl_renderer:
        return {"vendor": config.webgl_vendor, "renderer": config.webgl_renderer}
    return random.choice(WEBGL_CONFIGS)


def _webgl_spoof_script(webgl_config: dict) -> str:
    """Generate WebGL spoofing script"""
    vendor = webgl_config["vendor"]
    renderer = webgl_config["renderer"]

    return f"""
// WebGL Vendor/Renderer Spoofing
(function() {{
    const getParameterOriginal = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {{
        if (parameter === 37445) {{ // UNMASKED_VENDOR_WEBGL
            return '{vendor}';
        }}
        if (parameter === 37446) {{ // UNMASKED_RENDERER_WEBGL
            return '{renderer}';
        }}
        return getParameterOriginal.call(this, parameter);
    }};

    const getParameter2Original = WebGL2RenderingContext.prototype.getParameter;
    WebGL2RenderingContext.prototype.getParameter = function(parameter) {{
        if (parameter === 37445) {{
            return '{vendor}';
        }}
        if (parameter === 37446) {{
            return '{renderer}';
        }}
        return getParameter2Original.call(this, parameter);
    }};
}})();
"""


def _audio_noise_script(noise_level: float) -> str:
    """Generate audio fingerprint noise script"""
    return f"""
// Audio Fingerprint Noise
(function() {{
    const originalGetChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function(channel) {{
        const data = originalGetChannelData.call(this, channel);
        const noise = {noise_level};

        for (let i = 0; i < data.length; i++) {{
            data[i] += (Math.random() - 0.5) * noise;
        }}

        return data;
    }};

    const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
    AudioContext.prototype.createAnalyser = function() {{
        const analyser = originalCreateAnalyser.call(this);
        const originalGetFloatFrequencyData = analyser.getFloatFrequencyData.bind(analyser);

        analyser.getFloatFrequencyData = function(array) {{
            originalGetFloatFrequencyData(array);
            const noise = {noise_level};
            for (let i = 0; i < array.length; i++) {{
                array[i] += (Math.random() - 0.5) * noise * 100;
            }}
        }};

        return analyser;
    }};
}})();
"""


def _navigator_spoof_script(config: StealthConfig) -> str:
    """Generate navigator property spoofing script"""
    platform = config.platform or random.choice(PLATFORMS)
    hardware_concurrency = config.hardware_concurrency or random.choice([4, 8, 12, 16])
    device_memory = config.device_memory or random.choice([4, 8, 16])
    languages = json.dumps(config.languages) if hasattr(config, 'languages') else '["en-US", "en"]'

    return f"""
// Navigator Property Spoofing
(function() {{
    const navigatorProps = {{
        platform: '{platform}',
        hardwareConcurrency: {hardware_concurrency},
        deviceMemory: {device_memory},
        language: '{config.language}',
        languages: {languages},
        webdriver: false,
        maxTouchPoints: 0,
    }};

    for (const [key, value] of Object.entries(navigatorProps)) {{
        try {{
            Object.defineProperty(navigator, key, {{
                get: () => value,
                configurable: true,
            }});
        }} catch (e) {{}}
    }}

    // Hide webdriver
    Object.defineProperty(navigator, 'webdriver', {{
        get: () => undefined,
        configurable: true,
    }});

    // Chrome-specific
    if (window.chrome) {{
        window.chrome.runtime = undefined;
    }}

    // Remove automation indicators
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
    delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
}})();
"""


def _webrtc_block_script() -> str:
    """Generate WebRTC leak prevention script"""
    return """
// WebRTC Leak Prevention
(function() {
    // Block RTCPeerConnection
    const originalRTCPeerConnection = window.RTCPeerConnection;

    window.RTCPeerConnection = function(...args) {
        const pc = new originalRTCPeerConnection(...args);

        // Block local candidate gathering
        const originalAddIceCandidate = pc.addIceCandidate.bind(pc);
        pc.addIceCandidate = function(candidate) {
            if (candidate && candidate.candidate) {
                // Filter out local IP candidates
                if (candidate.candidate.includes('host') ||
                    candidate.candidate.match(/([0-9]{1,3}\\.){3}[0-9]{1,3}/)) {
                    return Promise.resolve();
                }
            }
            return originalAddIceCandidate(candidate);
        };

        return pc;
    };

    window.RTCPeerConnection.prototype = originalRTCPeerConnection.prototype;

    // Block webkitRTCPeerConnection
    if (window.webkitRTCPeerConnection) {
        window.webkitRTCPeerConnection = window.RTCPeerConnection;
    }
})();
"""


def _timezone_spoof_script(timezone: str) -> str:
    """Generate timezone spoofing script"""
    return f"""
// Timezone Spoofing
(function() {{
    const targetTimezone = '{timezone}';

    // Override Date.prototype methods
    const originalToString = Date.prototype.toString;
    const originalToLocaleString = Date.prototype.toLocaleString;
    const originalGetTimezoneOffset = Date.prototype.getTimezoneOffset;

    // Calculate offset for target timezone
    const now = new Date();
    const tzDate = new Date(now.toLocaleString('en-US', {{ timeZone: targetTimezone }}));
    const offset = (now.getTime() - tzDate.getTime()) / 60000;

    Date.prototype.getTimezoneOffset = function() {{
        return offset;
    }};

    // Override Intl.DateTimeFormat
    const originalResolvedOptions = Intl.DateTimeFormat.prototype.resolvedOptions;
    Intl.DateTimeFormat.prototype.resolvedOptions = function() {{
        const options = originalResolvedOptions.call(this);
        options.timeZone = targetTimezone;
        return options;
    }};
}})();
"""


def _plugins_spoof_script() -> str:
    """Generate plugin spoofing script"""
    return """
// Plugin Spoofing
(function() {
    // Create fake plugins array
    const fakePlugins = [
        {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format'},
        {name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: ''},
        {name: 'Native Client', filename: 'internal-nacl-plugin', description: ''},
    ];

    const pluginArray = {
        length: fakePlugins.length,
        item: function(index) { return this[index]; },
        namedItem: function(name) {
            return fakePlugins.find(p => p.name === name);
        },
        refresh: function() {},
    };

    fakePlugins.forEach((plugin, index) => {
        pluginArray[index] = plugin;
    });

    Object.defineProperty(navigator, 'plugins', {
        get: () => pluginArray,
        configurable: true,
    });

    // Spoof mimeTypes
    Object.defineProperty(navigator, 'mimeTypes', {
        get: () => ({
            length: 2,
            item: function(index) { return this[index]; },
            namedItem: function() { return null; },
            0: {type: 'application/pdf', suffixes: 'pdf', description: ''},
            1: {type: 'text/pdf', suffixes: 'pdf', description: ''},
        }),
        configurable: true,
    });
})();
"""


# Need to import json for the navigator script
import json


class StealthBrowser:
    """
    Stealth browser wrapper with anti-detection measures.

    Example:
        from playwright.async_api import async_playwright

        config = StealthConfig(
            canvas_noise=True,
            webgl_spoof=True,
            webrtc_block=True,
        )

        stealth = StealthBrowser(config)

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()

            # Apply stealth to context
            await stealth.apply_to_context(context)

            page = await context.new_page()
            await page.goto("https://example.com")
    """

    def __init__(self, config: Optional[StealthConfig] = None):
        self.config = config or StealthConfig()
        self._scripts: Optional[str] = None

    def get_scripts(self, seed: Optional[str] = None) -> str:
        """Get stealth injection scripts"""
        if self._scripts is None or seed:
            self._scripts = generate_stealth_scripts(self.config, seed)
        return self._scripts

    async def apply_to_context(self, context, seed: Optional[str] = None) -> None:
        """
        Apply stealth measures to a browser context.

        Args:
            context: Playwright BrowserContext
            seed: Optional seed for deterministic spoofing
        """
        scripts = self.get_scripts(seed)

        # Add initialization script
        await context.add_init_script(scripts)

        logger.debug("Applied stealth scripts to browser context")

    async def apply_to_page(self, page, seed: Optional[str] = None) -> None:
        """
        Apply stealth measures to a specific page.

        Args:
            page: Playwright Page
            seed: Optional seed for deterministic spoofing
        """
        scripts = self.get_scripts(seed)

        # Evaluate scripts on page
        await page.evaluate(scripts)

        logger.debug("Applied stealth scripts to page")

    def get_launch_args(self) -> list[str]:
        """Get recommended browser launch arguments for stealth"""
        args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
            "--disable-web-security",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--disable-gpu",
            "--window-size=1920,1080",
            "--start-maximized",
            "--hide-scrollbars",
            "--mute-audio",
        ]

        if self.config.webrtc_block:
            args.append("--disable-webrtc")

        return args

    def get_context_options(self) -> dict:
        """Get recommended context options for stealth"""
        options = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": None,  # Let UA manager handle this
            "locale": self.config.language,
            "timezone_id": self.config.timezone or random.choice(TIMEZONES),
            "permissions": [],
            "geolocation": None,
            "color_scheme": "light",
            "reduced_motion": "no-preference",
            "forced_colors": "none",
        }

        return options