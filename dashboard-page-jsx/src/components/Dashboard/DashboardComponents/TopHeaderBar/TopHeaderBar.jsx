import React from 'react';
function TopHeaderBar() {
  return (
    <div className="flex justify-between items-center p-4 bg-gray-100 border-b border-gray-300">
      <h2 className="text-lg font-bold">User Dashboard</h2>
      <div className="flex items-center">
        <span className="mr-2">Welcome, Alex Johnson</span>
        <button className="bg-gray-200 hover:bg-gray-300 py-2 px-4 rounded">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>
    </div>
  );
}
export default TopHeaderBar;