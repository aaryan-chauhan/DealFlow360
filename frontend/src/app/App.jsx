import { useSelector } from 'react-redux'
import { Navigate, Route, Routes } from 'react-router-dom'

import LoginPage from '../auth/LoginPage'
import SignupPage from '../auth/SignupPage'
import { selectIsAuthenticated } from '../auth/authSlice'
import DiscountConfigPage from '../features/admin/DiscountConfigPage'
import ProductsPage from '../features/admin/ProductsPage'
import ApprovalDetailPage from '../features/approvals/ApprovalDetailPage'
import ApprovalsListPage from '../features/approvals/ApprovalsListPage'
import QuotationBuilderPage from '../features/quotations/QuotationBuilderPage'
import QuotationsListPage from '../features/quotations/QuotationsListPage'
import PrivateRoute from '../routes/PrivateRoute'
import AppLayout from './AppLayout'
import SessionPlaceholder from './SessionPlaceholder'

function PublicOnly({ children }) {
  const isAuthenticated = useSelector(selectIsAuthenticated)
  return isAuthenticated ? <Navigate to="/dashboard" replace /> : children
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicOnly>
            <LoginPage />
          </PublicOnly>
        }
      />
      <Route
        path="/signup"
        element={
          <PublicOnly>
            <SignupPage />
          </PublicOnly>
        }
      />

      <Route
        element={
          <PrivateRoute>
            <AppLayout />
          </PrivateRoute>
        }
      >
        <Route path="/dashboard" element={<SessionPlaceholder />} />
        <Route path="/quotations" element={<QuotationsListPage />} />
        <Route path="/quotations/new" element={<QuotationBuilderPage />} />
        <Route path="/quotations/:id" element={<QuotationBuilderPage />} />
        <Route
          path="/approvals"
          element={
            <PrivateRoute roles={['sales_manager', 'finance_ops', 'admin']}>
              <ApprovalsListPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/approvals/:id"
          element={
            <PrivateRoute roles={['sales_manager', 'finance_ops', 'admin']}>
              <ApprovalDetailPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/admin/products"
          element={
            <PrivateRoute roles={['admin']}>
              <ProductsPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/admin/discount-config"
          element={
            <PrivateRoute roles={['admin', 'sales_manager']}>
              <DiscountConfigPage />
            </PrivateRoute>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}
