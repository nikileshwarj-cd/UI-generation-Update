import { useState } from 'react';
function useMainContentArea() {
  const [stats, setStats] = useState({
    totalProjects: 12,
    pendingTasks: 5,
    completedTasks: 38,
    notifications: 3
  });
  return { stats };
}
export default useMainContentArea;