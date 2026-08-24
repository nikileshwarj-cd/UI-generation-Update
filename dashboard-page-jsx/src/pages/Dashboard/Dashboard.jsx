import React from 'react';
import Sidebar from '../../components/Dashboard/DashboardComponents/Sidebar/Sidebar';
import TopHeaderBar from '../../components/Dashboard/DashboardComponents/TopHeaderBar/TopHeaderBar';
import MainContentArea from '../../components/Dashboard/DashboardComponents/MainContentArea/MainContentArea';
function Dashboard() {
  return (
    <div className="flex">
      <Sidebar />
      <div className="flex-1">
        <TopHeaderBar />
        <MainContentArea />
      </div>
    </div>
  );
}
export default Dashboard;