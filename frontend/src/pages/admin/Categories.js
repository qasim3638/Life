import React, { useEffect, useState } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { Plus, FolderOpen } from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Card } from '../../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../../components/ui/dialog';

export const AdminCategories = () => {
  const [categories, setCategories] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [formData, setFormData] = useState({ name: '', description: '' });

  useEffect(() => {
    fetchCategories();
  }, []);

  const fetchCategories = async () => {
    try {
      const response = await api.getCategories();
      setCategories(response.data);
    } catch (error) {
      toast.error('Failed to load categories');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      await api.createCategory(formData);
      toast.success('Category created successfully');
      setFormData({ name: '', description: '' });
      setOpen(false);
      fetchCategories();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Failed to create category');
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>;
  }

  return (
    <div className="space-y-6" data-testid="admin-categories-page">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl font-heading font-bold tracking-tightest mb-2">Categories</h1>
          <p className="text-muted-foreground">Organize your products</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button data-testid="add-category-btn" className="bg-accent hover:bg-accent/90">
              <Plus className="mr-2 h-4 w-4" /> Add Category
            </Button>
          </DialogTrigger>
          <DialogContent data-testid="category-dialog">
            <DialogHeader>
              <DialogTitle>Create Category</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="cat-name" data-testid="cat-name-label">Name *</Label>
                <Input
                  id="cat-name"
                  data-testid="cat-name-input"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                  placeholder="Category name"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="cat-description" data-testid="cat-description-label">Description</Label>
                <textarea
                  id="cat-description"
                  data-testid="cat-description-input"
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  placeholder="Category description"
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                />
              </div>
              <Button type="submit" data-testid="submit-category" className="w-full bg-accent hover:bg-accent/90">
                Create Category
              </Button>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {categories.length === 0 ? (
          <Card className="col-span-full p-12 text-center">
            <FolderOpen className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-20" />
            <p className="text-muted-foreground">No categories yet</p>
          </Card>
        ) : (
          categories.map(category => (
            <Card key={category.id} className="p-6 hover:shadow-md duration-200" data-testid={`category-${category.id}`}>
              <div className="flex items-start gap-3">
                <div className="p-2 bg-accent/10 rounded-md">
                  <FolderOpen className="h-5 w-5 text-accent" strokeWidth={1.5} />
                </div>
                <div className="flex-1">
                  <h3 className="font-heading font-bold tracking-tightest mb-1">{category.name}</h3>
                  <p className="text-sm text-muted-foreground">{category.description || 'No description'}</p>
                </div>
              </div>
            </Card>
          ))
        )}
      </div>
    </div>
  );
};
