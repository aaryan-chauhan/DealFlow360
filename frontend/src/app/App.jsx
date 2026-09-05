import { useSelector } from 'react-redux'
import { Navigate, Route, Routes } from 'react-router-dom'

import LoginPage from '../auth/LoginPage'
import SignupPage from '../auth/SignupPage'
import { selectIsAuthenticated } from '../auth/authSlice'
import DiscountConfigPage from '../features/admin/DiscountConfigPage'
import ProductsPage from '../features/admin/ProductsPage'
import SubscriptionPlansPage from '../features/admin/SubscriptionPlansPage'
import UpsellRulesPage from '../features/admin/UpsellRulesPage'
import WarehousesPage from '../features/admin/WarehousesPage'
import ApprovalDetailPage from '../features/approvals/ApprovalDetailPage'

import ApprovalsListPage from '../features/approvals/ApprovalsListPage'
import DashboardPage from '../features/dashboard/DashboardPage'
import FulfillmentDetailPage from '../features/fulfillment/FulfillmentDetailPage'
import FulfillmentListPage from '../features/fulfillment/FulfillmentListPage'
import InvoiceDetailPage from '../features/invoices/InvoiceDetailPage'
import InvoicesListPage from '../features/invoices/InvoicesListPage'
import QuotationBuilderPage from '../features/quotations/QuotationBuilderPage'
import QuotationsListPage from '../features/quotations/QuotationsListPage'
import BillingDetailPage from '../features/subscriptions/BillingDetailPage'
import SubscriptionsListPage from '../features/subscriptions/SubscriptionsListPage'
import DealHealthPage from '../features/dealHealth/DealHealthPage'
import ReportingPage from '../features/reporting/ReportingPage'
import PrivateRoute from '../routes/PrivateRoute'
import AppLayout from './AppLayout'

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
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/deal-health" element={<DealHealthPage />} />
        <Route path="/reports" element={<ReportingPage />} />
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
          path="/fulfillment"
          element={
            <PrivateRoute roles={['finance_ops', 'admin', 'sales_manager']}>
              <FulfillmentListPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/fulfillment/:id"
          element={
            <PrivateRoute roles={['finance_ops', 'admin', 'sales_manager']}>
              <FulfillmentDetailPage />
            </PrivateRoute>
          }
        />
        <Route path="/subscriptions" element={<SubscriptionsListPage />} />
        <Route path="/subscriptions/:id/billing" element={<BillingDetailPage />} />
        <Route path="/invoices" element={<InvoicesListPage />} />
        <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
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
        <Route
          path="/admin/warehouses"
          element={
            <PrivateRoute roles={['admin', 'finance_ops', 'sales_manager']}>
              <WarehousesPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/admin/subscription-plans"
          element={
            <PrivateRoute roles={['admin', 'finance_ops']}>
              <SubscriptionPlansPage />
            </PrivateRoute>
          }
        />
        <Route
          path="/admin/upsell-rules"
          element={
            <PrivateRoute roles={['admin', 'sales_manager']}>
              <UpsellRulesPage />
            </PrivateRoute>
          }
        />
      </Route>


      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}

