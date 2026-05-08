/**
 * NewOrderNotifier — invisible component that drives the new-order toast.
 * Mounted once globally inside <BrowserRouter>; the hook itself bails out
 * when no admin token is present.
 */
import useNewOrderNotifier from '../hooks/useNewOrderNotifier';

const NewOrderNotifier = () => {
  useNewOrderNotifier();
  return null;
};

export default NewOrderNotifier;
