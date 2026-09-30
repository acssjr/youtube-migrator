import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { DashboardLayout } from './layouts/DashboardLayout';
import { MigrationPage } from './pages/MigrationPage';
import { SettingsPage } from './pages/SettingsPage';
import { LogsPage } from './pages/LogsPage';
import { DescriptionsPage } from './pages/DescriptionsPage';
import { DownloadsPage } from './pages/DownloadsPage';
import { AcervoPage } from './pages/AcervoPage';
import { UploadsPage } from './pages/UploadsPage';

// Create TanStack Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export default function App() {
  const [activeTab, setActiveTab] = useState<string>(window.location.pathname === '/settings' || new URLSearchParams(window.location.search).has('auth') ? 'settings' : window.location.pathname === '/downloads' ? 'downloads' : window.location.pathname === '/acervo' ? 'acervo' : window.location.pathname === '/uploads' ? 'uploads' : 'descriptions');

  return (
    <QueryClientProvider client={queryClient}>
      <DashboardLayout activeTab={activeTab} setActiveTab={setActiveTab}>
        {activeTab === 'descriptions' && <DescriptionsPage />}
        {activeTab === 'downloads' && <DownloadsPage />}
        {activeTab === 'acervo' && <AcervoPage onNavigate={setActiveTab} />}
        {activeTab === 'uploads' && <UploadsPage />}
        {activeTab === 'migration' && <MigrationPage />}
        {activeTab === 'settings' && <SettingsPage />}
        {activeTab === 'logs' && <LogsPage />}
      </DashboardLayout>
    </QueryClientProvider>
  );
}
