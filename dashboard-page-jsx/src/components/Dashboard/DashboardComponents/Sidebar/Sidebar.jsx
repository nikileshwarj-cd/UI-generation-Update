import React from 'react';
function Sidebar() {
  return (
    <div className="w-64 bg-gray-800 text-white p-4">
      <h2 className="text-lg font-bold mb-4">Innovate Solutions Inc.</h2>
      <ul>
        <li className="mb-2"><a href="#" className="text-white hover:text-gray-300">Dashboard</a></li>
        <li className="mb-2"><a href="#" className="text-white hover:text-gray-300">Projects</a></li>
        <li className="mb-2"><a href="#" className="text-white hover:text-gray-300">Tasks</a></li>
        <li className="mb-2"><a href="#" className="text-white hover:text-gray-300">Notifications</a></li>
        <li className="mb-2"><a href="#" className="text-white hover:text-gray-300">Reports</a></li>
      </ul>
    </div>
  );
}
export default Sidebar;