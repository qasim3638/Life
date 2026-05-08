import React, { useState, useEffect } from 'react';
import { api } from '../../lib/api';
import { toast } from 'sonner';
import { 
  Plus, Search, CheckCircle, Clock, AlertTriangle, 
  Filter, Calendar, User, X, Edit2, Trash2, MessageSquare,
  ChevronDown, ChevronRight
} from 'lucide-react';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Card } from '../../components/ui/card';
import { useAuth } from '../../contexts/AuthContext';

const TasksNotes = () => {
  const { user } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [selectedTask, setSelectedTask] = useState(null);
  const [editingTask, setEditingTask] = useState(null);
  const [expandedTasks, setExpandedTasks] = useState(new Set());
  const [filters, setFilters] = useState({
    status: '',
    priority: '',
    search: ''
  });
  const [showrooms, setShowrooms] = useState([]);
  const [users, setUsers] = useState([]);

  const [taskForm, setTaskForm] = useState({
    title: '',
    description: '',
    priority: 'medium',
    due_date: '',
    assigned_to: '',
    assigned_to_name: '',
    showroom_id: '',
    showroom_name: '',
    category: 'general',
    related_customer: ''
  });

  const [noteContent, setNoteContent] = useState('');

  const priorities = [
    { value: 'low', label: 'Low', color: 'bg-gray-100 text-gray-700' },
    { value: 'medium', label: 'Medium', color: 'bg-blue-100 text-blue-700' },
    { value: 'high', label: 'High', color: 'bg-orange-100 text-orange-700' },
    { value: 'urgent', label: 'Urgent', color: 'bg-red-100 text-red-700' }
  ];

  const statuses = [
    { value: 'pending', label: 'Pending', icon: Clock, color: 'text-gray-500' },
    { value: 'in_progress', label: 'In Progress', icon: AlertTriangle, color: 'text-blue-500' },
    { value: 'completed', label: 'Completed', icon: CheckCircle, color: 'text-green-500' }
  ];

  const categories = [
    { value: 'general', label: 'General' },
    { value: 'follow_up', label: 'Follow Up' },
    { value: 'delivery', label: 'Delivery' },
    { value: 'payment', label: 'Payment' },
    { value: 'order', label: 'Order' },
    { value: 'complaint', label: 'Complaint' },
    { value: 'quote', label: 'Quote' }
  ];

  useEffect(() => {
    fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [tasksRes, statsRes, showroomsRes, usersRes] = await Promise.all([
        api.getTasks(filters),
        api.getTaskStats(),
        api.getShowrooms(),
        api.getUsers().catch(() => ({ data: [] }))
      ]);
      setTasks(tasksRes.data || []);
      setStats(statsRes.data || {});
      setShowrooms(showroomsRes.data || []);
      setUsers(usersRes.data || []);
    } catch (error) {
      toast.error('Failed to load tasks');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTask = async () => {
    if (!taskForm.title.trim()) {
      toast.error('Please enter a task title');
      return;
    }

    try {
      await api.createTask(taskForm);
      toast.success('Task created successfully');
      setShowCreateModal(false);
      resetTaskForm();
      fetchData();
    } catch (error) {
      toast.error('Failed to create task');
      console.error(error);
    }
  };

  const handleUpdateStatus = async (taskId, newStatus) => {
    try {
      await api.updateTask(taskId, { status: newStatus });
      toast.success(`Task marked as ${newStatus.replace('_', ' ')}`);
      fetchData();
    } catch (error) {
      toast.error('Failed to update task');
      console.error(error);
    }
  };

  const handleEditTask = (task) => {
    setEditingTask(task);
    setTaskForm({
      title: task.title || '',
      description: task.description || '',
      priority: task.priority || 'medium',
      due_date: task.due_date ? task.due_date.split('T')[0] : '',
      assigned_to: task.assigned_to || '',
      assigned_to_name: task.assigned_to_name || '',
      showroom_id: task.showroom_id || '',
      showroom_name: task.showroom_name || '',
      category: task.category || 'general',
      related_customer: task.related_customer || ''
    });
    setShowEditModal(true);
  };

  const handleUpdateTask = async () => {
    if (!taskForm.title.trim()) {
      toast.error('Please enter a task title');
      return;
    }

    try {
      await api.updateTask(editingTask.id, taskForm);
      toast.success('Task updated successfully');
      setShowEditModal(false);
      setEditingTask(null);
      resetTaskForm();
      fetchData();
    } catch (error) {
      toast.error('Failed to update task');
      console.error(error);
    }
  };

  const handleDeleteTask = async (taskId) => {
    if (!window.confirm('Are you sure you want to delete this task?')) return;

    try {
      await api.deleteTask(taskId);
      toast.success('Task deleted');
      fetchData();
    } catch (error) {
      toast.error('Failed to delete task');
      console.error(error);
    }
  };

  const handleAddNote = async () => {
    if (!noteContent.trim() || !selectedTask) return;

    try {
      await api.addTaskNote(selectedTask.id, { task_id: selectedTask.id, content: noteContent });
      toast.success('Note added');
      setNoteContent('');
      setShowNoteModal(false);
      // Refresh task to get new notes
      const res = await api.getTask(selectedTask.id);
      setSelectedTask(res.data);
      fetchData();
    } catch (error) {
      toast.error('Failed to add note');
      console.error(error);
    }
  };

  const resetTaskForm = () => {
    setTaskForm({
      title: '',
      description: '',
      priority: 'medium',
      due_date: '',
      assigned_to: '',
      assigned_to_name: '',
      showroom_id: '',
      showroom_name: '',
      category: 'general',
      related_customer: ''
    });
  };

  const toggleTaskExpand = async (taskId) => {
    const newExpanded = new Set(expandedTasks);
    if (newExpanded.has(taskId)) {
      newExpanded.delete(taskId);
    } else {
      newExpanded.add(taskId);
      // Fetch task details with notes
      try {
        const res = await api.getTask(taskId);
        setTasks(prev => prev.map(t => t.id === taskId ? { ...t, notes: res.data.notes } : t));
      } catch (error) {
        console.error('Failed to load task notes', error);
      }
    }
    setExpandedTasks(newExpanded);
  };

  const getPriorityBadge = (priority) => {
    const p = priorities.find(pr => pr.value === priority);
    return p ? `${p.color} px-2 py-1 rounded-full text-xs font-medium` : '';
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    return new Date(dateStr).toLocaleDateString('en-GB', { 
      day: '2-digit', month: 'short', year: 'numeric' 
    });
  };

  const isOverdue = (task) => {
    if (!task.due_date || task.status === 'completed') return false;
    return new Date(task.due_date) < new Date();
  };

  return (
    <div className="space-y-6" data-testid="tasks-notes-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-2xl font-bold">Tasks & Notes</h1>
          <p className="text-muted-foreground">Manage tasks and add notes for follow-ups</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)} data-testid="create-task-btn">
          <Plus className="mr-2 h-4 w-4" /> New Task
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
        <Card className="p-4 text-center">
          <p className="text-2xl font-bold">{stats.total || 0}</p>
          <p className="text-sm text-muted-foreground">Total</p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-2xl font-bold text-gray-600">{stats.pending || 0}</p>
          <p className="text-sm text-muted-foreground">Pending</p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-2xl font-bold text-blue-600">{stats.in_progress || 0}</p>
          <p className="text-sm text-muted-foreground">In Progress</p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-2xl font-bold text-green-600">{stats.completed || 0}</p>
          <p className="text-sm text-muted-foreground">Completed</p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-2xl font-bold text-red-600">{stats.overdue || 0}</p>
          <p className="text-sm text-muted-foreground">Overdue</p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-2xl font-bold text-orange-600">{stats.high_priority || 0}</p>
          <p className="text-sm text-muted-foreground">High Priority</p>
        </Card>
      </div>

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-wrap gap-4">
          <div className="flex-1 min-w-[200px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search tasks..."
                value={filters.search}
                onChange={(e) => setFilters({ ...filters, search: e.target.value })}
                className="pl-10"
                data-testid="search-tasks-input"
              />
            </div>
          </div>
          <select
            value={filters.status}
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
            className="h-10 px-3 rounded-md border border-input bg-background"
            data-testid="filter-status"
          >
            <option value="">All Status</option>
            {statuses.map(s => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
          <select
            value={filters.priority}
            onChange={(e) => setFilters({ ...filters, priority: e.target.value })}
            className="h-10 px-3 rounded-md border border-input bg-background"
            data-testid="filter-priority"
          >
            <option value="">All Priority</option>
            {priorities.map(p => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
        </div>
      </Card>

      {/* Tasks List */}
      <Card>
        {loading ? (
          <div className="p-8 text-center text-muted-foreground">Loading tasks...</div>
        ) : tasks.length === 0 ? (
          <div className="p-8 text-center text-muted-foreground">
            No tasks found. Create your first task!
          </div>
        ) : (
          <div className="divide-y">
            {tasks.map(task => (
              <div key={task.id} className={`p-4 ${isOverdue(task) ? 'bg-red-50' : ''}`}>
                <div className="flex items-start gap-4">
                  <button
                    onClick={() => toggleTaskExpand(task.id)}
                    className="mt-1 text-muted-foreground hover:text-foreground"
                  >
                    {expandedTasks.has(task.id) ? (
                      <ChevronDown className="h-5 w-5" />
                    ) : (
                      <ChevronRight className="h-5 w-5" />
                    )}
                  </button>
                  
                  <div className="flex-1">
                    <div className="flex flex-wrap items-center gap-2 mb-1">
                      <h3 className={`font-medium ${task.status === 'completed' ? 'line-through text-muted-foreground' : ''}`}>
                        {task.title}
                      </h3>
                      <span className={getPriorityBadge(task.priority)}>
                        {task.priority}
                      </span>
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        task.status === 'completed' ? 'bg-green-100 text-green-700' :
                        task.status === 'in_progress' ? 'bg-blue-100 text-blue-700' :
                        'bg-gray-100 text-gray-700'
                      }`}>
                        {task.status?.replace('_', ' ')}
                      </span>
                      {isOverdue(task) && (
                        <span className="px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-700">
                          Overdue
                        </span>
                      )}
                    </div>
                    
                    {task.description && (
                      <p className="text-sm text-muted-foreground mb-2 whitespace-pre-wrap">{task.description}</p>
                    )}
                    
                    <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
                      {task.due_date && (
                        <span className="flex items-center gap-1">
                          <Calendar className="h-3 w-3" />
                          Due: {formatDate(task.due_date)}
                        </span>
                      )}
                      {task.assigned_to_name && (
                        <span className="flex items-center gap-1">
                          <User className="h-3 w-3" />
                          {task.assigned_to_name}
                        </span>
                      )}
                      {task.showroom_name && (
                        <span>{task.showroom_name}</span>
                      )}
                      {task.category && (
                        <span className="px-2 py-0.5 bg-secondary rounded">{task.category}</span>
                      )}
                      {task.notes?.length > 0 && (
                        <span className="flex items-center gap-1">
                          <MessageSquare className="h-3 w-3" />
                          {task.notes.length} notes
                        </span>
                      )}
                    </div>

                    {/* Expanded Notes Section */}
                    {expandedTasks.has(task.id) && (
                      <div className="mt-4 pl-4 border-l-2 border-gray-200">
                        <div className="flex justify-between items-center mb-2">
                          <h4 className="font-medium text-sm">Notes</h4>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => {
                              setSelectedTask(task);
                              setShowNoteModal(true);
                            }}
                          >
                            <Plus className="h-3 w-3 mr-1" /> Add Note
                          </Button>
                        </div>
                        {task.notes?.length > 0 ? (
                          <div className="space-y-2">
                            {task.notes.map(note => (
                              <div key={note.id} className="bg-secondary/50 p-3 rounded-lg text-sm">
                                <p>{note.content}</p>
                                <p className="text-xs text-muted-foreground mt-1">
                                  {note.created_by_name || note.created_by} • {formatDate(note.created_at)}
                                </p>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="text-sm text-muted-foreground">No notes yet</p>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    {task.status !== 'completed' && (
                      <>
                        {task.status === 'pending' && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleUpdateStatus(task.id, 'in_progress')}
                          >
                            Start
                          </Button>
                        )}
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-green-600"
                          onClick={() => handleUpdateStatus(task.id, 'completed')}
                        >
                          <CheckCircle className="h-4 w-4" />
                        </Button>
                      </>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-blue-600"
                      onClick={() => handleEditTask(task)}
                      data-testid={`edit-task-${task.id}`}
                    >
                      <Edit2 className="h-4 w-4" />
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-600"
                      onClick={() => handleDeleteTask(task.id)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Create Task Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-bold">Create New Task</h2>
                <button onClick={() => setShowCreateModal(false)}>
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Title *</label>
                  <Input
                    value={taskForm.title}
                    onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })}
                    placeholder="Enter task title"
                    data-testid="task-title-input"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Description</label>
                  <textarea
                    value={taskForm.description}
                    onChange={(e) => setTaskForm({ ...taskForm, description: e.target.value })}
                    placeholder="Enter task description"
                    className="w-full h-24 px-3 py-2 rounded-md border border-input bg-background resize-none"
                    data-testid="task-description-input"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Priority</label>
                    <select
                      value={taskForm.priority}
                      onChange={(e) => setTaskForm({ ...taskForm, priority: e.target.value })}
                      className="w-full h-10 px-3 rounded-md border border-input bg-background"
                      data-testid="task-priority-select"
                    >
                      {priorities.map(p => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1">Category</label>
                    <select
                      value={taskForm.category}
                      onChange={(e) => setTaskForm({ ...taskForm, category: e.target.value })}
                      className="w-full h-10 px-3 rounded-md border border-input bg-background"
                      data-testid="task-category-select"
                    >
                      {categories.map(c => (
                        <option key={c.value} value={c.value}>{c.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Due Date</label>
                  <Input
                    type="date"
                    value={taskForm.due_date}
                    onChange={(e) => setTaskForm({ ...taskForm, due_date: e.target.value })}
                    data-testid="task-due-date-input"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Assign To</label>
                  <select
                    value={taskForm.assigned_to}
                    onChange={(e) => {
                      const selectedUser = users.find(u => u.email === e.target.value);
                      setTaskForm({ 
                        ...taskForm, 
                        assigned_to: e.target.value,
                        assigned_to_name: selectedUser?.name || ''
                      });
                    }}
                    className="w-full h-10 px-3 rounded-md border border-input bg-background"
                    data-testid="task-assign-select"
                  >
                    <option value="">Unassigned</option>
                    {users.map(u => (
                      <option key={u.email} value={u.email}>{u.name || u.email}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Store</label>
                  <select
                    value={taskForm.showroom_id}
                    onChange={(e) => {
                      const selectedStore = showrooms.find(s => s.id === e.target.value);
                      setTaskForm({ 
                        ...taskForm, 
                        showroom_id: e.target.value,
                        showroom_name: selectedStore?.name || ''
                      });
                    }}
                    className="w-full h-10 px-3 rounded-md border border-input bg-background"
                    data-testid="task-store-select"
                  >
                    <option value="">Select store</option>
                    {showrooms.map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Related Customer</label>
                  <Input
                    value={taskForm.related_customer}
                    onChange={(e) => setTaskForm({ ...taskForm, related_customer: e.target.value })}
                    placeholder="Customer name or phone"
                    data-testid="task-customer-input"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 mt-6">
                <Button variant="outline" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button onClick={handleCreateTask} data-testid="save-task-btn">
                  Create Task
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Edit Task Modal */}
      {showEditModal && editingTask && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-lg font-bold">Edit Task</h2>
                <button onClick={() => { setShowEditModal(false); setEditingTask(null); resetTaskForm(); }}>
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Title *</label>
                  <Input
                    value={taskForm.title}
                    onChange={(e) => setTaskForm({ ...taskForm, title: e.target.value })}
                    placeholder="Enter task title"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Description</label>
                  <textarea
                    value={taskForm.description}
                    onChange={(e) => setTaskForm({ ...taskForm, description: e.target.value })}
                    placeholder="Enter task description (line breaks will be preserved)"
                    className="w-full h-32 px-3 py-2 rounded-md border border-input bg-background resize-none font-mono text-sm"
                  />
                  <p className="text-xs text-muted-foreground mt-1">Line breaks and spacing will be preserved</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Priority</label>
                    <select
                      value={taskForm.priority}
                      onChange={(e) => setTaskForm({ ...taskForm, priority: e.target.value })}
                      className="w-full h-10 px-3 rounded-md border border-input bg-background"
                    >
                      {priorities.map(p => (
                        <option key={p.value} value={p.value}>{p.label}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1">Category</label>
                    <select
                      value={taskForm.category}
                      onChange={(e) => setTaskForm({ ...taskForm, category: e.target.value })}
                      className="w-full h-10 px-3 rounded-md border border-input bg-background"
                    >
                      {categories.map(c => (
                        <option key={c.value} value={c.value}>{c.label}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Due Date</label>
                  <Input
                    type="date"
                    value={taskForm.due_date}
                    onChange={(e) => setTaskForm({ ...taskForm, due_date: e.target.value })}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Assign To</label>
                  <select
                    value={taskForm.assigned_to}
                    onChange={(e) => {
                      const selectedUser = users.find(u => u.email === e.target.value);
                      setTaskForm({ 
                        ...taskForm, 
                        assigned_to: e.target.value,
                        assigned_to_name: selectedUser?.name || ''
                      });
                    }}
                    className="w-full h-10 px-3 rounded-md border border-input bg-background"
                  >
                    <option value="">Unassigned</option>
                    {users.map(u => (
                      <option key={u.email} value={u.email}>{u.name || u.email}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Store</label>
                  <select
                    value={taskForm.showroom_id}
                    onChange={(e) => {
                      const selectedStore = showrooms.find(s => s.id === e.target.value);
                      setTaskForm({ 
                        ...taskForm, 
                        showroom_id: e.target.value,
                        showroom_name: selectedStore?.name || ''
                      });
                    }}
                    className="w-full h-10 px-3 rounded-md border border-input bg-background"
                  >
                    <option value="">Select store</option>
                    {showrooms.map(s => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Related Customer</label>
                  <Input
                    value={taskForm.related_customer}
                    onChange={(e) => setTaskForm({ ...taskForm, related_customer: e.target.value })}
                    placeholder="Customer name or phone"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-3 mt-6">
                <Button variant="outline" onClick={() => { setShowEditModal(false); setEditingTask(null); resetTaskForm(); }}>
                  Cancel
                </Button>
                <Button onClick={handleUpdateTask} data-testid="update-task-btn">
                  Save Changes
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Add Note Modal */}
      {showNoteModal && selectedTask && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <Card className="w-full max-w-md">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-lg font-bold">Add Note</h2>
                <button onClick={() => setShowNoteModal(false)}>
                  <X className="h-5 w-5" />
                </button>
              </div>

              <p className="text-sm text-muted-foreground mb-4">
                Adding note to: <strong>{selectedTask.title}</strong>
              </p>

              <textarea
                value={noteContent}
                onChange={(e) => setNoteContent(e.target.value)}
                placeholder="Enter your note..."
                className="w-full h-32 px-3 py-2 rounded-md border border-input bg-background resize-none"
                data-testid="note-content-input"
              />

              <div className="flex justify-end gap-3 mt-4">
                <Button variant="outline" onClick={() => setShowNoteModal(false)}>
                  Cancel
                </Button>
                <Button onClick={handleAddNote} data-testid="save-note-btn">
                  Add Note
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default TasksNotes;
