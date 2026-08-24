import { useState } from 'react';
function useNotificationsPanel() {
  const [notifications, setNotifications] = useState([
    { id: 1, type: 'Task', name: 'New task assigned in 'Product Launch'' },
    { id: 2, type: 'Task', name: 'New task assigned in 'Product Launch'' }
  ]);
  return { notifications };
}
export default useNotificationsPanel;