"""
Human Behavior - Human-like mouse movement and interaction patterns

Features:
- Bezier curve mouse movement
- Variable speed profiles
- Realistic click patterns
- Human-like typing
- Random micro-movements
"""
from __future__ import annotations

import asyncio
import math
import random
from dataclasses import dataclass, field
from typing import Optional, Tuple
from loguru import logger


@dataclass
class Point:
    """2D point"""
    x: float
    y: float

    def __add__(self, other: "Point") -> "Point":
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Point") -> "Point":
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Point":
        return Point(self.x * scalar, self.y * scalar)

    def distance_to(self, other: "Point") -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def to_tuple(self) -> Tuple[float, float]:
        return (self.x, self.y)


@dataclass
class HumanBehaviorConfig:
    """Configuration for human-like behavior"""
    # Mouse movement
    mouse_speed_min: float = 0.5  # Minimum speed multiplier
    mouse_speed_max: float = 1.5  # Maximum speed multiplier
    mouse_acceleration: float = 0.8  # Acceleration curve
    mouse_jitter: float = 2.0  # Random jitter in pixels

    # Bezier curve
    bezier_control_points: int = 2  # Number of control points
    bezier_deviation: float = 0.3  # How far control points deviate from line

    # Click behavior
    click_delay_min: float = 0.05  # Minimum delay before click
    click_delay_max: float = 0.15  # Maximum delay before click
    double_click_interval: float = 0.1  # Interval between double clicks

    # Typing behavior
    typing_speed_min: float = 0.05  # Minimum delay between keys
    typing_speed_max: float = 0.15  # Maximum delay between keys
    typo_rate: float = 0.02  # Probability of making a typo
    typo_correction_delay: float = 0.3  # Delay before correcting typo

    # Scrolling
    scroll_speed_min: float = 50  # Minimum scroll amount
    scroll_speed_max: float = 200  # Maximum scroll amount
    scroll_pause_min: float = 0.1  # Minimum pause between scrolls
    scroll_pause_max: float = 0.5  # Maximum pause between scrolls

    # Micro-movements
    micro_movement_enabled: bool = True
    micro_movement_radius: float = 3.0
    micro_movement_interval: float = 0.5


def bezier_curve(
    start: Point,
    end: Point,
    control_points: list[Point],
    steps: int = 50,
) -> list[Point]:
    """
    Generate points along a Bezier curve.

    Args:
        start: Starting point
        end: Ending point
        control_points: Control points for the curve
        steps: Number of points to generate

    Returns:
        List of points along the curve
    """
    points = [start] + control_points + [end]
    n = len(points) - 1

    def bernstein(i: int, n: int, t: float) -> float:
        """Bernstein polynomial"""
        return math.comb(n, i) * (t ** i) * ((1 - t) ** (n - i))

    curve_points = []
    for step in range(steps + 1):
        t = step / steps
        x = sum(bernstein(i, n, t) * points[i].x for i in range(n + 1))
        y = sum(bernstein(i, n, t) * points[i].y for i in range(n + 1))
        curve_points.append(Point(x, y))

    return curve_points


def generate_control_points(
    start: Point,
    end: Point,
    num_points: int = 2,
    deviation: float = 0.3,
) -> list[Point]:
    """
    Generate random control points for a Bezier curve.

    Args:
        start: Starting point
        end: Ending point
        num_points: Number of control points
        deviation: How far points can deviate from the line

    Returns:
        List of control points
    """
    control_points = []
    distance = start.distance_to(end)

    for i in range(num_points):
        # Position along the line
        t = (i + 1) / (num_points + 1)

        # Base position on the line
        base_x = start.x + (end.x - start.x) * t
        base_y = start.y + (end.y - start.y) * t

        # Random deviation perpendicular to the line
        angle = math.atan2(end.y - start.y, end.x - start.x) + math.pi / 2
        dev = (random.random() - 0.5) * 2 * deviation * distance

        x = base_x + math.cos(angle) * dev
        y = base_y + math.sin(angle) * dev

        control_points.append(Point(x, y))

    return control_points


def apply_speed_profile(
    points: list[Point],
    acceleration: float = 0.8,
) -> list[Tuple[Point, float]]:
    """
    Apply human-like speed profile to points.

    Returns points with delay times that simulate:
    - Slow start (acceleration)
    - Fast middle
    - Slow end (deceleration)

    Args:
        points: List of points
        acceleration: Acceleration curve factor

    Returns:
        List of (point, delay) tuples
    """
    n = len(points)
    if n <= 1:
        return [(p, 0.01) for p in points]

    result = []
    for i, point in enumerate(points):
        # Normalized position (0 to 1)
        t = i / (n - 1)

        # Bell curve speed profile: slow-fast-slow
        # Using sine wave for smooth acceleration/deceleration
        speed = math.sin(t * math.pi) ** acceleration

        # Avoid division by zero
        speed = max(speed, 0.1)

        # Convert to delay (inverse of speed)
        delay = 0.01 / speed

        # Add some randomness
        delay *= random.uniform(0.8, 1.2)

        result.append((point, delay))

    return result


class HumanMouse:
    """
    Human-like mouse controller.

    Example:
        from playwright.async_api import Page

        mouse = HumanMouse()

        # Move to element with human-like motion
        await mouse.move_to_element(page, "#submit-button")

        # Click with realistic timing
        await mouse.click(page)

        # Or combine: move and click
        await mouse.move_and_click(page, "#submit-button")
    """

    def __init__(self, config: Optional[HumanBehaviorConfig] = None):
        self.config = config or HumanBehaviorConfig()
        self._current_position = Point(0, 0)

    async def move_to(
        self,
        page,
        target: Point,
        speed_multiplier: float = 1.0,
    ) -> None:
        """
        Move mouse to target with human-like motion.

        Args:
            page: Playwright page
            target: Target position
            speed_multiplier: Speed adjustment (higher = faster)
        """
        start = self._current_position

        # Calculate distance for timing
        distance = start.distance_to(target)

        # Generate control points for Bezier curve
        control_points = generate_control_points(
            start,
            target,
            num_points=self.config.bezier_control_points,
            deviation=self.config.bezier_deviation,
        )

        # Calculate number of steps based on distance
        steps = max(10, int(distance / 10))

        # Generate curve points
        curve_points = bezier_curve(start, target, control_points, steps)

        # Apply speed profile
        points_with_delays = apply_speed_profile(
            curve_points,
            self.config.mouse_acceleration,
        )

        # Add jitter and move
        speed = random.uniform(
            self.config.mouse_speed_min,
            self.config.mouse_speed_max,
        ) * speed_multiplier

        for point, delay in points_with_delays:
            # Add micro-jitter
            jitter_x = random.uniform(-self.config.mouse_jitter, self.config.mouse_jitter)
            jitter_y = random.uniform(-self.config.mouse_jitter, self.config.mouse_jitter)

            final_x = point.x + jitter_x
            final_y = point.y + jitter_y

            await page.mouse.move(final_x, final_y)
            await asyncio.sleep(delay / speed)

        self._current_position = target

    async def move_to_element(
        self,
        page,
        selector: str,
        offset: Optional[Tuple[float, float]] = None,
    ) -> bool:
        """
        Move mouse to element with human-like motion.

        Args:
            page: Playwright page
            selector: Element selector
            offset: Optional (x, y) offset from element center

        Returns:
            True if element found and moved to
        """
        try:
            element = page.locator(selector)
            box = await element.bounding_box()

            if not box:
                logger.warning(f"Element not found or not visible: {selector}")
                return False

            # Calculate target position (center of element with offset)
            target_x = box["x"] + box["width"] / 2
            target_y = box["y"] + box["height"] / 2

            if offset:
                target_x += offset[0]
                target_y += offset[1]

            # Add small random offset for more natural positioning
            target_x += random.uniform(-5, 5)
            target_y += random.uniform(-5, 5)

            await self.move_to(page, Point(target_x, target_y))
            return True

        except Exception as e:
            logger.error(f"Failed to move to element: {e}")
            return False

    async def click(
        self,
        page,
        button: str = "left",
        click_count: int = 1,
    ) -> None:
        """
        Perform human-like click.

        Args:
            page: Playwright page
            button: Mouse button ('left', 'right', 'middle')
            click_count: Number of clicks (1 for single, 2 for double)
        """
        # Pre-click delay
        delay = random.uniform(
            self.config.click_delay_min,
            self.config.click_delay_max,
        )
        await asyncio.sleep(delay)

        if click_count == 2:
            # Double click with realistic interval
            await page.mouse.click(
                self._current_position.x,
                self._current_position.y,
                button=button,
            )
            await asyncio.sleep(self.config.double_click_interval)
            await page.mouse.click(
                self._current_position.x,
                self._current_position.y,
                button=button,
            )
        else:
            await page.mouse.click(
                self._current_position.x,
                self._current_position.y,
                button=button,
                click_count=click_count,
            )

    async def move_and_click(
        self,
        page,
        selector: str,
        button: str = "left",
        click_count: int = 1,
    ) -> bool:
        """
        Move to element and click with human-like behavior.

        Args:
            page: Playwright page
            selector: Element selector
            button: Mouse button
            click_count: Number of clicks

        Returns:
            True if successful
        """
        if await self.move_to_element(page, selector):
            await self.click(page, button, click_count)
            return True
        return False

    async def drag_to(
        self,
        page,
        start_selector: str,
        end_selector: str,
    ) -> bool:
        """
        Drag from one element to another.

        Args:
            page: Playwright page
            start_selector: Starting element
            end_selector: Ending element

        Returns:
            True if successful
        """
        try:
            # Move to start element
            if not await self.move_to_element(page, start_selector):
                return False

            # Mouse down
            await page.mouse.down()
            await asyncio.sleep(random.uniform(0.05, 0.1))

            # Get end position
            element = page.locator(end_selector)
            box = await element.bounding_box()
            if not box:
                await page.mouse.up()
                return False

            target = Point(
                box["x"] + box["width"] / 2 + random.uniform(-5, 5),
                box["y"] + box["height"] / 2 + random.uniform(-5, 5),
            )

            # Drag with slower speed
            await self.move_to(page, target, speed_multiplier=0.5)

            # Mouse up
            await asyncio.sleep(random.uniform(0.05, 0.1))
            await page.mouse.up()

            return True

        except Exception as e:
            logger.error(f"Drag failed: {e}")
            await page.mouse.up()
            return False


class HumanTyping:
    """
    Human-like typing simulator.

    Example:
        typing = HumanTyping()

        # Type with realistic speed and occasional typos
        await typing.type_text(page, "#search-input", "hello world")
    """

    def __init__(self, config: Optional[HumanBehaviorConfig] = None):
        self.config = config or HumanBehaviorConfig()

        # Common typo patterns (key -> likely mistype)
        self._typo_map = {
            'a': ['s', 'q', 'z'],
            's': ['a', 'd', 'w'],
            'd': ['s', 'f', 'e'],
            'e': ['w', 'r', 'd'],
            'r': ['e', 't', 'f'],
            't': ['r', 'y', 'g'],
            'i': ['u', 'o', 'k'],
            'o': ['i', 'p', 'l'],
            'n': ['b', 'm', 'h'],
            'm': ['n', ',', 'j'],
        }

    async def type_text(
        self,
        page,
        selector: str,
        text: str,
        clear_first: bool = True,
    ) -> bool:
        """
        Type text with human-like behavior.

        Args:
            page: Playwright page
            selector: Input element selector
            text: Text to type
            clear_first: Clear existing text first

        Returns:
            True if successful
        """
        try:
            element = page.locator(selector)

            # Focus element
            await element.click()
            await asyncio.sleep(random.uniform(0.1, 0.2))

            # Clear existing text
            if clear_first:
                await page.keyboard.press("Control+a")
                await asyncio.sleep(random.uniform(0.05, 0.1))
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.1, 0.2))

            # Type each character
            for char in text:
                # Check for typo
                if random.random() < self.config.typo_rate and char.lower() in self._typo_map:
                    # Make typo
                    typo_char = random.choice(self._typo_map[char.lower()])
                    await page.keyboard.type(typo_char)

                    # Pause to "realize" mistake
                    await asyncio.sleep(self.config.typo_correction_delay)

                    # Correct typo
                    await page.keyboard.press("Backspace")
                    await asyncio.sleep(random.uniform(0.05, 0.1))

                # Type correct character
                await page.keyboard.type(char)

                # Variable delay between keys
                delay = random.uniform(
                    self.config.typing_speed_min,
                    self.config.typing_speed_max,
                )

                # Longer delay after space or punctuation
                if char in ' .,!?':
                    delay *= 1.5

                await asyncio.sleep(delay)

            return True

        except Exception as e:
            logger.error(f"Typing failed: {e}")
            return False

    async def press_key(
        self,
        page,
        key: str,
        modifiers: Optional[list[str]] = None,
    ) -> None:
        """
        Press a key with human-like timing.

        Args:
            page: Playwright page
            key: Key to press
            modifiers: Optional modifier keys ['Control', 'Shift', 'Alt']
        """
        # Pre-press delay
        await asyncio.sleep(random.uniform(0.05, 0.15))

        if modifiers:
            for mod in modifiers:
                await page.keyboard.down(mod)

        await page.keyboard.press(key)

        if modifiers:
            for mod in reversed(modifiers):
                await page.keyboard.up(mod)


class HumanScroll:
    """
    Human-like scrolling behavior.
    """

    def __init__(self, config: Optional[HumanBehaviorConfig] = None):
        self.config = config or HumanBehaviorConfig()

    async def scroll_to_element(
        self,
        page,
        selector: str,
    ) -> bool:
        """
        Scroll to element with human-like behavior.

        Args:
            page: Playwright page
            selector: Element selector

        Returns:
            True if element found
        """
        try:
            element = page.locator(selector)
            box = await element.bounding_box()

            if not box:
                return False

            # Get viewport
            viewport = page.viewport_size

            # Calculate scroll needed
            target_y = box["y"] - viewport["height"] / 2

            # Current scroll position
            current_scroll = await page.evaluate("window.scrollY")

            # Scroll in chunks
            scroll_distance = target_y - current_scroll
            num_scrolls = max(3, int(abs(scroll_distance) / 200))

            for i in range(num_scrolls):
                # Calculate this scroll amount
                amount = scroll_distance / num_scrolls

                # Add randomness
                amount += random.uniform(-30, 30)

                await page.mouse.wheel(0, amount)

                # Pause between scrolls
                pause = random.uniform(
                    self.config.scroll_pause_min,
                    self.config.scroll_pause_max,
                )
                await asyncio.sleep(pause)

            return True

        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return False

    async def scroll_page(
        self,
        page,
        direction: str = "down",
        amount: Optional[int] = None,
    ) -> None:
        """
        Scroll page with human-like behavior.

        Args:
            page: Playwright page
            direction: 'up' or 'down'
            amount: Scroll amount (random if None)
        """
        if amount is None:
            amount = random.randint(
                int(self.config.scroll_speed_min),
                int(self.config.scroll_speed_max),
            )

        if direction == "up":
            amount = -amount

        await page.mouse.wheel(0, amount)


class HumanBehavior:
    """
    Combined human behavior controller.

    Example:
        human = HumanBehavior()

        # Move and click like a human
        await human.mouse.move_and_click(page, "#login-button")

        # Type like a human
        await human.typing.type_text(page, "#username", "myuser")

        # Scroll like a human
        await human.scroll.scroll_to_element(page, "#footer")
    """

    def __init__(self, config: Optional[HumanBehaviorConfig] = None):
        self.config = config or HumanBehaviorConfig()
        self.mouse = HumanMouse(self.config)
        self.typing = HumanTyping(self.config)
        self.scroll = HumanScroll(self.config)

    async def random_pause(
        self,
        min_seconds: float = 0.5,
        max_seconds: float = 2.0,
    ) -> None:
        """Add a random pause like a human would"""
        await asyncio.sleep(random.uniform(min_seconds, max_seconds))

    async def micro_movement(self, page) -> None:
        """Perform small random mouse movement"""
        if not self.config.micro_movement_enabled:
            return

        current = self.mouse._current_position
        offset_x = random.uniform(
            -self.config.micro_movement_radius,
            self.config.micro_movement_radius,
        )
        offset_y = random.uniform(
            -self.config.micro_movement_radius,
            self.config.micro_movement_radius,
        )

        await page.mouse.move(current.x + offset_x, current.y + offset_y)
        self.mouse._current_position = Point(current.x + offset_x, current.y + offset_y)