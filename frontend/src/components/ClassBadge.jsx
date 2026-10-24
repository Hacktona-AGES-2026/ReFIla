export default function ClassBadge({ classe }) {
  return <span className={`class-badge classe-${classe}`}>{classe}</span>;
}
