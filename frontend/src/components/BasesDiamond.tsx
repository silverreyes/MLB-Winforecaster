interface BasesDiamondProps {
  runner_on_1b: boolean;
  runner_on_2b: boolean;
  runner_on_3b: boolean;
}

function describeRunners(first: boolean, second: boolean, third: boolean): string {
  const bases: string[] = [];
  if (first) bases.push('first');
  if (second) bases.push('second');
  if (third) bases.push('third');
  if (bases.length === 0) return 'Bases empty';
  return `Runners on ${bases.join(' and ')}`;
}

export function BasesDiamond({ runner_on_1b, runner_on_2b, runner_on_3b }: BasesDiamondProps) {
  const occupied = '#F59E0B';  // --color-accent
  const empty = 'none';
  const stroke = '#1E1E2A';        // --color-border (basepaths, home plate)
  const emptyStroke = '#8A8A9A';   // visible outline for unoccupied bases

  return (
    <svg viewBox="0 0 80 80" width="80" height="80" role="img"
         aria-label={describeRunners(runner_on_1b, runner_on_2b, runner_on_3b)}>
      {/* Basepaths */}
      <line x1="40" y1="72" x2="64" y2="40" stroke={stroke} strokeWidth="1" />
      <line x1="64" y1="40" x2="40" y2="8" stroke={stroke} strokeWidth="1" />
      <line x1="40" y1="8" x2="16" y2="40" stroke={stroke} strokeWidth="1" />
      <line x1="16" y1="40" x2="40" y2="72" stroke={stroke} strokeWidth="1" />
      {/* Home plate */}
      <polygon points="40,78 34,72 34,68 46,68 46,72"
               fill="none" stroke={stroke} strokeWidth="1.5" />
      {/* 1st base */}
      <rect x="58" y="34" width="12" height="12" rx="1"
            transform="rotate(45, 64, 40)"
            fill={runner_on_1b ? occupied : empty}
            stroke={runner_on_1b ? stroke : emptyStroke} strokeWidth="1.5" />
      {/* 2nd base */}
      <rect x="34" y="2" width="12" height="12" rx="1"
            transform="rotate(45, 40, 8)"
            fill={runner_on_2b ? occupied : empty}
            stroke={runner_on_2b ? stroke : emptyStroke} strokeWidth="1.5" />
      {/* 3rd base */}
      <rect x="10" y="34" width="12" height="12" rx="1"
            transform="rotate(45, 16, 40)"
            fill={runner_on_3b ? occupied : empty}
            stroke={runner_on_3b ? stroke : emptyStroke} strokeWidth="1.5" />
    </svg>
  );
}
