import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from './stores/authStore'
import Layout from './components/Layout'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import VMsPage from './pages/VMsPage'
import CreateVMPage from './pages/CreateVMPage'
import VMDetailPage from './pages/VMDetailPage'
import ClustersPage from './pages/ClustersPage'
import CreateClusterPage from './pages/CreateClusterPage'
import OrganizationSettingsPage from './pages/OrganizationSettingsPage'
import QuotaPage from './pages/QuotaPage'
import ISOUploadPage from './pages/ISOUploadPage'
import NetworksPage from './pages/NetworksPage'
import ContainersPage from './pages/ContainersPage'

function App() {
  const { isAuthenticated } = useAuthStore()

  return (
    <Routes>
      <Route
        path="/login"
        element={isAuthenticated ? <Navigate to="/dashboard" /> : <LoginPage />}
      />
      <Route
        path="/dashboard"
        element={
          isAuthenticated ? (
            <Layout>
              <DashboardPage />
            </Layout>
          ) : (
            <Navigate to="/login" />
          )
        }
      />
      <Route
        path="/vms"
        element={
          isAuthenticated ? (
            <Layout>
              <VMsPage />
            </Layout>
          ) : (
            <Navigate to="/login" />
          )
        }
      />
      <Route
        path="/vms/create"
        element={
          isAuthenticated ? (
            <Layout>
              <CreateVMPage />
            </Layout>
          ) : (
            <Navigate to="/login" />
          )
        }
      />
      <Route
        path="/vms/:vmId"
        element={
          isAuthenticated ? (
            <Layout>
              <VMDetailPage />
            </Layout>
          ) : (
            <Navigate to="/login" />
          )
        }
      />
      <Route
        path="/templates"
        element={<Navigate to="/vm-templates/isos" replace />}
      />
      <Route
        path="/vm-templates"
        element={<Navigate to="/vm-templates/isos" replace />}
      />
      <Route
        path="/vm-templates/isos"
        element={
          isAuthenticated ? (
            <Layout>
              <ISOUploadPage />
            </Layout>
          ) : (
            <Navigate to="/login" />
          )
        }
      />
      <Route
        path="/clusters"
        element={
          isAuthenticated ? (
            <Layout>
              <ClustersPage />
            </Layout>
          ) : (
            <Navigate to="/login" />
          )
        }
      />
      <Route
        path="/clusters/create"
        element={
          isAuthenticated ? (
            <Layout>
              <CreateClusterPage />
            </Layout>
          ) : (
            <Navigate to="/login" />
          )
        }
      />
      <Route
        path="/quotas"
        element={
          isAuthenticated ? (
            <Layout>
              <QuotaPage />
            </Layout>
          ) : (
            <Navigate to="/login" />
          )
        }
      />
      <Route
        path="/containers"
        element={
          isAuthenticated ? (
            <Layout>
              <ContainersPage />
            </Layout>
          ) : (
            <Navigate to="/login" />
          )
        }
      />
      <Route
        path="/networking"
        element={
          isAuthenticated ? (
            <Layout>
              <NetworksPage />
            </Layout>
          ) : (
            <Navigate to="/login" />
          )
        }
      />
      <Route
        path="/organization/settings"
        element={
          isAuthenticated ? (
            <Layout>
              <OrganizationSettingsPage />
            </Layout>
          ) : (
            <Navigate to="/login" />
          )
        }
      />
      <Route
        path="/"
        element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} />}
      />
    </Routes>
  )
}

export default App
