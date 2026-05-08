import { 
  Percent, Gift, Award, Truck, Headphones, Shield, 
  ShoppingBag, Heart, CheckCircle2, Package, MapPin, 
  User, Building2, Wallet, TrendingUp, CreditCard,
  Clock, FileText
} from 'lucide-react';

const ICON_MAP = {
  Percent, Gift, Award, Truck, Headphones, Shield,
  ShoppingBag, Heart, CheckCircle2, Package, MapPin,
  User, Building2, Wallet, TrendingUp, CreditCard,
  Clock, FileText
};

export const getIcon = (name) => ICON_MAP[name] || ShoppingBag;
