"""
Chart Generator — Creates professional trading charts from live market data.

Used specifically for the ai_trading niche.
Generates candlestick charts, volume bars, and dashboard-style images.
"""
from datetime import datetime
from pathlib import Path

from config import OUTPUT_DIR


def generate_candlestick_chart(
    symbol: str,
    period: str = "3mo",
    interval: str = "1d",
    output_path: Path | None = None,
    style: str = "nightclouds",
    show_volume: bool = True,
    show_mav: tuple = (20, 50),
    width: int = 19.2,
    height: int = 10.8,
    dpi: int = 150,
) -> str | None:
    """
    Generate a candlestick chart for a given stock/crypto symbol.

    Returns: path to saved image, or None on failure
    """
    try:
        import yfinance as yf
        import mplfinance as mpf

        # Fetch data
        ticker = yf.Ticker(symbol)
        data = ticker.history(period=period, interval=interval)

        if data.empty:
            print(f"[Chart] No data for {symbol}")
            return None

        # Custom market colors
        mc = mpf.make_marketcolors(
            up="#00ff88",
            down="#ff4444",
            edge="inherit",
            wick="inherit",
            volume="in",
        )
        s = mpf.make_mpf_style(marketcolors=mc, base_mpf_style=style)

        # Output path
        if output_path is None:
            output_path = OUTPUT_DIR / "charts" / f"{symbol.replace('-', '_')}_{period}.png"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate chart
        save_config = dict(fname=str(output_path), dpi=dpi, bbox_inches="tight")
        mpf.plot(
            data,
            type="candle",
            style=s,
            volume=show_volume,
            mav=show_mav,
            title=f"\n{symbol} — {period.upper()} Chart",
            figsize=(width, height),
            savefig=save_config,
        )

        print(f"[Chart] Generated: {output_path.name} ({symbol})")
        return str(output_path)

    except Exception as e:
        print(f"[Chart] Failed to generate chart for {symbol}: {e}")
        return None


def generate_dashboard_image(
    symbols: list[str],
    output_path: Path | None = None,
    period: str = "1mo",
) -> str | None:
    """
    Generate a multi-symbol trading dashboard image using Plotly.

    Returns: path to saved image, or None on failure
    """
    try:
        import yfinance as yf
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        # Fetch data for all symbols
        rows = min(len(symbols), 4)
        fig = make_subplots(
            rows=rows, cols=1,
            shared_xaxes=True,
            subplot_titles=[f"{s}" for s in symbols[:rows]],
            vertical_spacing=0.08,
        )

        for i, symbol in enumerate(symbols[:rows], 1):
            data = yf.Ticker(symbol).history(period=period, interval="1d")
            if data.empty:
                continue

            fig.add_trace(
                go.Candlestick(
                    x=data.index,
                    open=data["Open"],
                    high=data["High"],
                    low=data["Low"],
                    close=data["Close"],
                    name=symbol,
                    increasing_line_color="#00ff88",
                    decreasing_line_color="#ff4444",
                ),
                row=i, col=1,
            )

        fig.update_layout(
            template="plotly_dark",
            height=300 * rows,
            width=1920,
            showlegend=False,
            xaxis_rangeslider_visible=False,
            title=dict(
                text=f"Market Dashboard — {datetime.now().strftime('%B %d, %Y')}",
                font=dict(size=24, color="white"),
            ),
            paper_bgcolor="#0a0a1a",
            plot_bgcolor="#0a0a1a",
        )

        # Remove range sliders from all subplots
        for i in range(1, rows + 1):
            fig.update_xaxes(rangeslider_visible=False, row=i, col=1)

        if output_path is None:
            output_path = OUTPUT_DIR / "charts" / "dashboard.png"
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        fig.write_image(str(output_path), scale=2)
        print(f"[Chart] Dashboard generated: {output_path.name}")
        return str(output_path)

    except Exception as e:
        print(f"[Chart] Dashboard generation failed: {e}")
        return None


def generate_price_summary(symbols: list[str]) -> str:
    """
    Get a text summary of current prices for AI script context.

    Returns: formatted string with price data
    """
    try:
        import yfinance as yf

        lines = []
        for symbol in symbols:
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            hist = ticker.history(period="5d")

            if hist.empty:
                continue

            current = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2] if len(hist) > 1 else current
            change = ((current - prev) / prev) * 100

            direction = "up" if change > 0 else "down"
            lines.append(
                f"{symbol}: ${current:.2f} ({direction} {abs(change):.1f}%)"
            )

        return "\n".join(lines) if lines else "Market data unavailable"

    except Exception as e:
        print(f"[Chart] Price summary failed: {e}")
        return "Market data unavailable"


async def generate_charts_for_niche(
    symbols: list[str],
    output_dir: Path,
) -> list[str]:
    """
    Generate all charts needed for a trading video.

    Returns: list of chart image paths
    """
    output_dir = Path(output_dir)
    charts = []

    # Individual candlestick charts
    for symbol in symbols[:5]:  # Max 5 charts
        path = generate_candlestick_chart(
            symbol,
            period="3mo",
            output_path=output_dir / f"chart_{symbol.replace('-', '_')}.png",
        )
        if path:
            charts.append(path)

    # Dashboard overview
    dashboard = generate_dashboard_image(
        symbols[:4],
        output_path=output_dir / "dashboard.png",
    )
    if dashboard:
        charts.append(dashboard)

    return charts


# CLI test
if __name__ == "__main__":
    import asyncio

    async def test():
        charts = await generate_charts_for_niche(
            ["SPY", "AAPL", "BTC-USD"],
            OUTPUT_DIR / "test_charts",
        )
        print(f"Generated {len(charts)} charts")
        for c in charts:
            print(f"  -> {c}")

        summary = generate_price_summary(["SPY", "QQQ", "AAPL", "BTC-USD"])
        print(f"\nPrice Summary:\n{summary}")

    asyncio.run(test())
