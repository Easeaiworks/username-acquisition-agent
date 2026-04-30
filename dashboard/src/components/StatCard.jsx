export default function StatCard({ label, value, sub, trend, icon: Icon, color = 'blue' }) {
  const iconColors = {
    blue: '#3a5289',
    green: '#059669',
    amber: '#d97706',
    red: '#dc2626',
    purple: '#7c3aed',
  };

  return (
    <div className="glass-card rounded-xl p-5 cursor-default">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium" style={{ color: '#6b7a99' }}>{label}</p>
          <p className="text-2xl font-bold mt-1" style={{ color: '#1b2a4a' }}>{value}</p>
          {sub && <p className="text-xs mt-1" style={{ color: '#9aa5bd' }}>{sub}</p>}
        </div>
        {Icon && (
          <div className="stat-icon p-2.5 rounded-lg">
            <Icon size={20} style={{ color: iconColors[color] || iconColors.blue }} />
          </div>
        )}
      </div>
      {trend !== undefined && (
        <p className={`text-xs mt-3 font-medium ${trend >= 0 ? 'text-green-600' : 'text-red-500'}`}>
          {trend >= 0 ? '↑' : '↓'} {Math.abs(trend)}% vs last week
        </p>
      )}
    </div>
  );
}
