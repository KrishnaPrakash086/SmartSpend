// Resolves CSS custom properties into concrete chart styles for Recharts
export function useChartTheme() {
  // Reads computed CSS variables on every render so charts react to theme changes instantly
  const getStyle = () => {
    const root = getComputedStyle(document.documentElement);
    const get = (v: string) => root.getPropertyValue(v).trim();
    return {
      tickFill: `hsl(${get("--chart-tick")})`,
      tooltipStyle: {
        background: `hsl(${get("--chart-tooltip-bg")})`,
        border: `1px solid hsl(${get("--chart-tooltip-border")})`,
        borderRadius: "8px",
        color: `hsl(${get("--chart-tooltip-text")})`,
      },
    };
  };

  return getStyle();
}
