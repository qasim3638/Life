import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { ShoppingCart } from 'lucide-react';
import { Card } from '../../components/ui/card';
import { Button } from '../../components/ui/button';

export const AdminOrders = () => {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchOrders();
  }, []);

  const fetchOrders = async () => {
    try {
      const response = await api.getOrders();
      setOrders(response.data);
    } catch (error) {
      toast.error('Failed to load orders');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusUpdate = async (orderId, newStatus) => {
    try {
      await api.updateOrderStatus(orderId, newStatus);
      toast.success('Order status updated');
      fetchOrders();
    } catch (error) {
      toast.error('Failed to update order status');
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>;
  }

  return (
    <div className="space-y-6" data-testid="admin-orders-page">
      <div>
        <h1 className="text-4xl font-heading font-bold tracking-tightest mb-2">Orders</h1>
        <p className="text-muted-foreground">Manage customer orders</p>
      </div>

      <div className="space-y-4">
        {orders.length === 0 ? (
          <Card className="p-12 text-center">
            <ShoppingCart className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-20" />
            <p className="text-muted-foreground">No orders yet</p>
          </Card>
        ) : (
          orders.map(order => (
            <Card key={order.id} className="p-6" data-testid={`order-${order.id}`}>
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                <div className="lg:col-span-8 space-y-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Order ID</p>
                      <p className="font-mono text-sm">{order.id}</p>
                    </div>
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                      order.status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                      order.status === 'processing' ? 'bg-blue-100 text-blue-800' :
                      order.status === 'completed' ? 'bg-emerald-100 text-emerald-800' :
                      order.status === 'cancelled' ? 'bg-red-100 text-red-800' :
                      'bg-gray-100 text-gray-800'
                    }`} data-testid={`order-status-${order.id}`}>
                      {order.status}
                    </span>
                  </div>

                  <div>
                    <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-1">Customer</p>
                    <p className="font-medium">{order.customer_name}</p>
                    <p className="text-sm text-muted-foreground">{order.customer_email}</p>
                  </div>

                  <div>
                    <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-2">Items</p>
                    <div className="space-y-2">
                      {order.items.map((item, idx) => (
                        <div key={idx} className="flex items-center justify-between p-3 bg-secondary rounded-md">
                          <div>
                            <p className="font-medium text-sm">{item.product_name}</p>
                            <p className="text-xs text-muted-foreground">Qty: {item.quantity}</p>
                          </div>
                          <p className="font-mono tabular-nums">£{(item.price * item.quantity).toFixed(2)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="lg:col-span-4 space-y-4">
                  <div className="p-4 bg-secondary rounded-md">
                    <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-2">Total Amount</p>
                    <p className="text-3xl font-heading font-bold tracking-tightest tabular-nums">£{order.total_amount.toFixed(2)}</p>
                  </div>

                  <div className="p-4 bg-secondary rounded-md">
                    <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-2">Order Date</p>
                    <p className="text-sm">{new Date(order.created_at).toLocaleDateString()}</p>
                    <p className="text-xs text-muted-foreground">{new Date(order.created_at).toLocaleTimeString()}</p>
                  </div>

                  <div className="space-y-2">
                    <p className="text-xs font-mono uppercase tracking-widest text-muted-foreground mb-2">Update Status</p>
                    <select
                      value={order.status}
                      onChange={(e) => handleStatusUpdate(order.id, e.target.value)}
                      className="w-full px-3 py-2 rounded-md border border-input bg-background text-sm"
                      data-testid={`status-select-${order.id}`}
                    >
                      <option value="pending">Pending</option>
                      <option value="processing">Processing</option>
                      <option value="completed">Completed</option>
                      <option value="cancelled">Cancelled</option>
                    </select>
                  </div>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};
