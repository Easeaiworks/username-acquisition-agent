const VARIANTS = {
  green: 'bg-green-100 text-green-800',
  red: 'bg-red-100 text-red-800',
  amber: 'bg-amber-100 text-amber-800',
  blue: 'bg-blue-100 text-blue-800',
  purple: 'bg-purple-100 text-purple-800',
  gray: 'bg-gray-100 text-gray-700',
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
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${VARIANTS[color] || VARIANTS.gray}`}>
      {children}
    </span>
  );
}
