import { useState } from 'react';
function useRecentActivity() {
  const [activity, setActivity] = useState([
    { id: 1, type: 'Project', name: 'Marketing Campaign', timestamp: '2 mins ago' },
    { id: 2, type: 'Task', name: 'API Integration', timestamp: '1 hr ago' },
    { id: 3, type: 'Notification', name: 'Notification Received', timestamp: '3 hrs ago' }
  ]);
  return { activity };
}
export default useRecentActivity;