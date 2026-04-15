"""Demo application for cjm-fasthtml-virtual-scrollbar library.

Showcases the virtual scrollbar component with a simple navigable list.
Keyboard (Up/Down/PageUp/PageDown/Home/End) and scrollbar (drag/click)
navigation both work and stay in sync.

Run with: python demo_app.py
"""

from dataclasses import dataclass
from typing import List


# =============================================================================
# Configuration
# =============================================================================

DEMO_PORT = 5035
DEFAULT_ITEM_COUNT = 500
DEFAULT_VISIBLE_COUNT = 20


# =============================================================================
# Demo State & Data
# =============================================================================

@dataclass
class DemoState:
    """Mutable state for the scrollbar demo."""
    position: int = 0
    visible_count: int = 15
    total_items: int = 500


def _generate_items(count: int) -> List[str]:
    """Generate numbered demo items."""
    return [f"Item {i}: {'=' * (10 + (i % 20))}" for i in range(count)]


def _navigate(state: DemoState, direction: str) -> None:
    """Update state.position based on direction."""
    if direction == 'up':
        state.position = max(0, state.position - 1)
    elif direction == 'down':
        state.position = min(state.total_items - 1, state.position + 1)
    elif direction == 'page_up':
        state.position = max(0, state.position - state.visible_count)
    elif direction == 'page_down':
        state.position = min(state.total_items - 1, state.position + state.visible_count)
    elif direction == 'first':
        state.position = 0
    elif direction == 'last':
        state.position = state.total_items - 1


def _navigate_to_index(state: DemoState, index: int) -> None:
    """Jump to a specific index."""
    state.position = max(0, min(index, state.total_items - 1))


# =============================================================================
# Demo Application
# =============================================================================

def main():
    """Initialize scrollbar demo and return the app."""
    from fasthtml.common import fast_app, Div, H1, P, Hidden, Script, APIRouter

    from cjm_fasthtml_daisyui.core.resources import get_daisyui_headers
    from cjm_fasthtml_daisyui.core.testing import create_theme_persistence_script
    from cjm_fasthtml_daisyui.utilities.semantic_colors import bg_dui, text_dui, border_dui
    from cjm_fasthtml_daisyui.utilities.border_radius import border_radius

    from cjm_fasthtml_tailwind.utilities.spacing import p, m
    from cjm_fasthtml_tailwind.utilities.sizing import max_w, min_h, h
    from cjm_fasthtml_tailwind.utilities.typography import font_size, font_weight, text_align
    from cjm_fasthtml_tailwind.utilities.layout import overflow
    from cjm_fasthtml_tailwind.utilities.flexbox_and_grid import flex_display, grow, gap
    from cjm_fasthtml_tailwind.utilities.borders import border
    from cjm_fasthtml_tailwind.core.base import combine_classes

    from cjm_fasthtml_app_core.components.navbar import create_navbar
    from cjm_fasthtml_app_core.core.routing import register_routes
    from cjm_fasthtml_app_core.core.htmx import handle_htmx_request
    from cjm_fasthtml_app_core.core.layout import wrap_with_layout

    from cjm_fasthtml_virtual_scrollbar.core.models import (
        ScrollbarConfig, ScrollbarState, ScrollbarIds,
    )
    from cjm_fasthtml_virtual_scrollbar.components.scrollbar import render_scrollbar
    from cjm_fasthtml_virtual_scrollbar.js.scrollbar import generate_scrollbar_js

    print("\n" + "=" * 70)
    print("Initializing cjm-fasthtml-virtual-scrollbar Demo")
    print("=" * 70)

    # =========================================================================
    # App setup
    # =========================================================================

    APP_ID = "vscroll"
    PREFIX = "demo"
    POSITION_INPUT_ID = f"{PREFIX}-position-input"
    VIEWPORT_ID = f"{PREFIX}-viewport"
    PROGRESS_ID = f"{PREFIX}-progress"
    INTERACT_ID = f"{PREFIX}-interact-indicator"
    ON_INTERACT_CB = f"on{PREFIX.capitalize()}ScrollbarInteract"

    app, rt = fast_app(
        pico=False,
        hdrs=[*get_daisyui_headers(), create_theme_persistence_script()],
        title="Virtual Scrollbar Demo",
        htmlkw={'data-theme': 'light'},
        session_cookie=f'session_{APP_ID}_',
        secret_key=f'{APP_ID}-demo-secret',
    )

    router = APIRouter(prefix="/demo")

    # =========================================================================
    # State
    # =========================================================================

    state = DemoState(
        position=0,
        visible_count=DEFAULT_VISIBLE_COUNT,
        total_items=DEFAULT_ITEM_COUNT,
    )
    items = _generate_items(DEFAULT_ITEM_COUNT)

    # Cursor-based scrollbar (matches card-stack & virtual-collection):
    # position == focused item index (0..total-1), thumb is a proportional
    # position indicator rather than a window-size proxy. auto_hide disabled
    # so the thumb is always visible, even when visible_count >= total_items.
    sb_config = ScrollbarConfig(prefix=PREFIX, track_width=3, auto_hide=False)
    sb_ids = ScrollbarIds(prefix=PREFIX)

    # =========================================================================
    # Render helpers
    # =========================================================================

    def _render_viewport_items():
        """Render the visible slice of items as Div rows."""
        start = max(0, state.position)
        end = min(state.total_items, start + state.visible_count)

        rows = []
        for i in range(start, end):
            is_focused = (i == state.position)
            cls = combine_classes(
                p.x(3), p.y(2),
                border.b(), border_dui.base_300,
                bg_dui.primary.opacity(20) if is_focused else '',
                text_dui.base_content,
            )
            rows.append(Div(items[i], cls=cls))
        return rows

    def _sb_state() -> ScrollbarState:
        """Build ScrollbarState from demo state (cursor-based model)."""
        return ScrollbarState(
            position=state.position,
            visible_count=state.visible_count,
            total_items=state.total_items,
            max_position=max(0, state.total_items - 1),
            thumb_ratio=1.0 / max(1, state.total_items),
        )

    def _render_viewport():
        """Render the item viewport container."""
        return Div(
            *_render_viewport_items(),
            id=VIEWPORT_ID,
            cls=combine_classes(overflow.y.hidden, grow(), min_h._0),
        )

    def _render_progress():
        """Render position indicator."""
        return Div(
            f"Item {state.position + 1} of {state.total_items}",
            id=PROGRESS_ID,
            cls=combine_classes(
                text_align.center, p.y(2),
                font_size.sm, text_dui.base_content.opacity(60),
            ),
        )

    def _render_hidden_input():
        """Render the hidden position input for scrollbar JS sync."""
        return Hidden(
            value=str(state.position),
            id=POSITION_INPUT_ID,
            name="position",
        )

    def _render_interact_indicator():
        """Render a badge that flashes on scrollbar interaction."""
        return Div(
            "Scrollbar idle",
            id=INTERACT_ID,
            cls=combine_classes(
                p.x(3), p.y(1),
                font_size.sm, text_dui.base_content.opacity(40),
                border._1, border_dui.base_300, border_radius.field,
                text_align.center,
            ),
        )

    def _interact_indicator_js():
        """JS callback that flashes the indicator on scrollbar interaction."""
        return f"""
        window['{ON_INTERACT_CB}'] = function() {{
            var el = document.getElementById('{INTERACT_ID}');
            if (!el) return;
            el.textContent = 'Scrollbar active';
            el.style.borderColor = 'oklch(var(--p))';
            el.style.color = 'oklch(var(--p))';
            el.style.opacity = '1';
            clearTimeout(window._interactTimer);
            window._interactTimer = setTimeout(function() {{
                el.textContent = 'Scrollbar idle';
                el.style.borderColor = '';
                el.style.color = '';
                el.style.opacity = '';
            }}, 800);
        }};
        """

    def _build_nav_response():
        """Build OOB response tuple after navigation."""
        viewport = _render_viewport()
        viewport.attrs["hx-swap-oob"] = "innerHTML"

        progress = _render_progress()
        progress.attrs["hx-swap-oob"] = "outerHTML"

        pos_input = _render_hidden_input()
        pos_input.attrs["hx-swap-oob"] = "outerHTML"

        scrollbar = render_scrollbar(_sb_state(), sb_config, sb_ids)
        scrollbar.attrs["hx-swap-oob"] = "outerHTML"

        return viewport, progress, pos_input, scrollbar

    # =========================================================================
    # Navigation routes
    # =========================================================================

    @router
    def nav_up(): return _do_nav('up')

    @router
    def nav_down(): return _do_nav('down')

    @router
    def nav_page_up(): return _do_nav('page_up')

    @router
    def nav_page_down(): return _do_nav('page_down')

    @router
    def nav_first(): return _do_nav('first')

    @router
    def nav_last(): return _do_nav('last')

    def _do_nav(direction):
        _navigate(state, direction)
        return _build_nav_response()

    @router
    def nav_to_index(target_index: int):
        _navigate_to_index(state, target_index)
        return _build_nav_response()

    # =========================================================================
    # Keyboard JS
    # =========================================================================

    NAV_URL_PREFIX = "/demo"

    def _keyboard_js():
        """Generate keyboard navigation JS."""
        return f"""
        (function() {{
            document.addEventListener('keydown', function(evt) {{
                const key = evt.key;
                let url = null;

                if (key === 'ArrowUp') url = '{NAV_URL_PREFIX}/nav_up';
                else if (key === 'ArrowDown') url = '{NAV_URL_PREFIX}/nav_down';
                else if (key === 'PageUp') url = '{NAV_URL_PREFIX}/nav_page_up';
                else if (key === 'PageDown') url = '{NAV_URL_PREFIX}/nav_page_down';
                else if (key === 'Home') url = '{NAV_URL_PREFIX}/nav_first';
                else if (key === 'End') url = '{NAV_URL_PREFIX}/nav_last';

                if (url) {{
                    evt.preventDefault();
                    htmx.ajax('POST', url, {{ swap: 'none' }});
                }}
            }});
        }})();
        """

    # =========================================================================
    # Page route
    # =========================================================================

    @router
    def index(request):
        """Demo page."""
        scrollbar_js = generate_scrollbar_js(
            ids=sb_ids,
            position_input_id=POSITION_INPUT_ID,
            nav_url=f"{NAV_URL_PREFIX}/nav_to_index",
            on_interact=ON_INTERACT_CB,
        )

        def page_content():
            return Div(
                H1("Virtual Scrollbar Demo",
                   cls=combine_classes(font_size._3xl, font_weight.bold, m.b(2))),
                P(f"{state.total_items} items — use keyboard "
                  f"(Up/Down/PgUp/PgDown/Home/End) or drag/click the scrollbar. "
                  f"The indicator below flashes on scrollbar interaction only.",
                  cls=combine_classes(
                      font_size.sm, text_dui.base_content.opacity(60), m.b(4),
                  )),

                # Main area: viewport + scrollbar side by side
                Div(
                    _render_viewport(),
                    render_scrollbar(_sb_state(), sb_config, sb_ids),
                    cls=combine_classes(
                        flex_display, gap(2),
                        border._1, border_dui.base_300,
                        bg_dui.base_100,
                        h(200)
                    ),
                ),

                # Progress + interaction indicator
                Div(
                    _render_progress(),
                    _render_interact_indicator(),
                    cls=combine_classes(flex_display, gap(4)),
                    style="align-items: center; justify-content: center;",
                ),

                # Hidden input for scrollbar position sync
                _render_hidden_input(),

                # Scripts
                Script(_keyboard_js()),
                Script(scrollbar_js),
                Script(_interact_indicator_js()),

                cls=combine_classes(max_w('4xl'), m.x.auto, p(6)),
            )

        return handle_htmx_request(
            request, page_content,
            wrap_fn=lambda content: wrap_with_layout(
                content, navbar=navbar,
            ),
        )

    # =========================================================================
    # Navbar and registration
    # =========================================================================

    navbar = create_navbar(
        title="Virtual Scrollbar Demo",
        nav_items=[("Demo", index)],
        home_route=index,
        theme_selector=True,
    )

    register_routes(app, router)

    print(f"\n  Items: {state.total_items}")
    print(f"  Visible: {state.visible_count}")
    print(f"  Port: {DEMO_PORT}")
    print(f"\n  URL: http://localhost:{DEMO_PORT}/demo")
    print("=" * 70 + "\n")

    return app


if __name__ == "__main__":
    import uvicorn

    app = main()
    uvicorn.run(app, host="0.0.0.0", port=DEMO_PORT)
