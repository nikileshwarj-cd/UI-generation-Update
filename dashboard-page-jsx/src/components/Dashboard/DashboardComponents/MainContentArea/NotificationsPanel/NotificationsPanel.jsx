import React from 'react';
function NotificationsPanel() {
  return (
    <div className="notifications-panel">
      <h2 className="text-lg font-bold">Notifications</h2>
      <ul>
        <li className="mb-2">New task assigned in 'Product Launch'</li>
        <li className="mb-2">New task assigned in 'Product Launch'</li>
      </ul>
      <button className="bg-gray-200 hover:bg-gray-300 py-2 px-4 rounded">View All</button>
    </div>
  );
}
export default NotificationsPanel;