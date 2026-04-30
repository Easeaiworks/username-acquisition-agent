const VARIANTS = {
  green: { background: 'linear-gradient(135deg, #d1fae5, #a7f3d0)', color: '#065f46', border: '1px solid rgba(6, 95, 70, 0.1)' },
  red: { background: 'linear-gradient(135deg, #fee2e2, #fecaca)', color: '#991b1b', border: '1px solid rgba(153, 27, 27, 0.1)' },
  amber: { background: 'linear-gradient(135deg, #fef3c7, #fde68a)', color: '#92400e', border: '1px solid rgba(146, 64, 14, 0.1)' },
  blue: { background: 'linear-gradient(135deg, #dbeafe, #bfdbfe)', color: '#1e40af', border: '1px solid rgba(30, 64, 175, 0.1)' },
  purple: { background: 'linear-gradient(135deg, #ede9fe, #ddd6fe)', color: '#5b21b6', border: '1px solid rgba(91, 33, 182, 0.1)' },
  gray: { background: 'linear-gradient(135deg, #f3f4f6, #e5e7eb)', color: '#374151', border: '1px solid rgba(55, 65, 81, 0.1)' },
};

const PRIORITY_MAP = {
  critical: 'red',
  very_high: 'amber',
  high: 'blue',
  medium: 'purple',
  low: 'gray',
};

const STATUS_MAP = {
  qualified: 'green',
  approval_queue: 'amber',
  outreach_active: 'blue',
  meeting_booked: 'green',
  rejected: 'red',
  parked: 'gray',
  new: 'purple',
  scanned: 'blue',
  scored: 'blue',
  enriched: 'green',
};

export function PriorityBadge({ priority }) {
  const color = PRIORITY_MAP[priority] || 'gray';
  const label = (priority || 'unknown').replace(/_/g, ' ');
  return <Badge color={color}>{label}</Badge>;
}

export function StatusBadge({ status }) {
  const color = STATUS_MAP[status] || 'gray';
  const label = (status || 'unknown').replace(/_/g, ' ');
  return <Badge color={color}>{label}</Badge>;
}

export default function Badge({ color = 'gray', children }) {
  const style = VARIANTS[color] || VARIANTS.gray;
  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize"
      style={style}
    >
      {children}
    </span>
  );
}
