
        #################################################
        ### THIS FILE WAS AUTOGENERATED! DO NOT EDIT! ###
        #################################################

from nb_003a import *
from typing import Dict, Any, AnyStr, List, Sequence, TypeVar, Tuple, Optional, Union
from torch import Tensor

Floats = Union[float, Collection[float]]
Rank0Tensor = typing.NewType('Rank0Tensor', Tensor)

class OptimWrapper():
    def __init__(self, opt, wd=0., true_wd=False):
        self.opt,self.true_wd = opt,true_wd
        self.opt_keys = list(self.opt.param_groups[0].keys())
        self.opt_keys.remove('params')
        self.read_defaults()
        self._wd = wd
    
    #Pytorch optimizer methods
    def step(self):
        # weight decay outside of optimizer step (AdamW)
        if self.true_wd:
            for pg in self.opt.param_groups:
                for p in pg['params']: p.data.mul_(1 - self._wd*pg['lr'])
            self.set_val('weight_decay', 0)
        self.opt.step()
    
    def zero_grad(self): self.opt.zero_grad()
    
    #Hyperparameters as properties
    @property
    def lr(self): return self._lr

    @lr.setter
    def lr(self, val): self._lr = self.set_val('lr', val)
    
    @property
    def mom(self): return self._mom

    @mom.setter
    def mom(self, val):
        if 'momentum' in self.opt_keys: self.set_val('momentum', val)
        elif 'betas' in self.opt_keys:  self.set_val('betas', (val, self._beta))
        self._mom = val
    
    @property
    def beta(self): return self._beta

    @beta.setter
    def beta(self, val):
        if 'betas' in self.opt_keys:    self.set_val('betas', (self._mom,val))
        elif 'alpha' in self.opt_keys:  self.set_val('alpha', val)
        self._beta = val
    
    @property
    def wd(self): return self._wd

    @wd.setter
    def wd(self, val):
        if not self.true_wd: self.set_val('weight_decay', val)
        self._wd = val
    
    #Helper functions
    def read_defaults(self):
        self._beta = None
        if 'lr' in self.opt_keys: self._lr = self.opt.param_groups[0]['lr']
        if 'momentum' in self.opt_keys: self._mom = self.opt.param_groups[0]['momentum']
        if 'alpha' in self.opt_keys: self._beta = self.opt.param_groups[0]['alpha']
        if 'betas' in self.opt_keys: self._mom,self._beta = self.opt.param_groups[0]['betas']
        if 'weight_decay' in self.opt_keys: self._wd = self.opt.param_groups[0]['weight_decay']
    
    def set_val(self, key, val):
        for pg in self.opt.param_groups: pg[key] = val
        return val

class Callback():
    def on_train_begin(self, **kwargs): pass         
        #To initiliaze constants in the callback.
    def on_epoch_begin(self, **kwargs): pass
        #At the beginning of each epoch
    def on_batch_begin(self, **kwargs): pass 
        #To set HP before the step is done. 
        #Returns xb, yb (which can allow us to modify the input at that step if needed)
    def on_loss_begin(self, **kwargs): pass
        #Called after the forward pass but before the loss has been computed.
        #Returns the output (which can allow us to modify it)
    def on_backward_begin(self, **kwargs): pass
        #Called after the forward pass and the loss has been computed, but before the back propagation.
        #Returns the loss (which can allow us to modify it, for instance for reg functions)
    def on_backward_end(self, **kwargs): pass
        #Called after the back propagation had been done (and the gradients computed) but before the step of the optimizer.
        #Useful for true weight decay in AdamW
    def on_step_end(self, **kwargs): pass
        #Called after the step of the optimizer but before the gradients are zeroed (not sure this one is useful)
    def on_batch_end(self, **kwargs): pass
        #Called at the end of the batch
    def on_epoch_end(self, **kwargs): pass
        #Called at the end of an epoch
    def on_train_end(self, **kwargs): pass
        #Useful for cleaning up things and saving files/models

class SmoothenValue():
    def __init__(self, beta):
        self.beta,self.n,self.mov_avg = beta,0,0
    
    def add_value(self, val):
        self.n += 1
        self.mov_avg = self.beta * self.mov_avg + (1 - self.beta) * val
        self.smooth = self.mov_avg / (1 - self.beta ** self.n)

def _get_init_state(): return {'epoch':0, 'iteration':0, 'num_batch':0}

@dataclass
class CallbackHandler():
    callbacks:Collection[Callable]
    beta:float=0.98
        
    def __post_init__(self):
        self.smoothener = SmoothenValue(self.beta)
        self.state_dict:Dict[str,Union[int,float,Tensor]]=_get_init_state()
    
    def __call__(self, cb_name):
        return [getattr(cb, f'on_{cb_name}')(**self.state_dict) for cb in self.callbacks]
    
    def on_train_begin(self): 
        self.state_dict = _get_init_state()
        self('train_begin')
        
    def on_epoch_begin(self): 
        self.state_dict['num_batch'] = 0
        self('epoch_begin')
        
    def on_batch_begin(self, xb, yb):
        self.state_dict['last_input'], self.state_dict['last_target'] = xb, yb
        for cb in self.callbacks:
            a = cb.on_batch_begin(**self.state_dict)
            if a is not None: self.state_dict['last_input'], self.state_dict['last_target'] = a
        return self.state_dict['last_input'], self.state_dict['last_target']
    
    def on_loss_begin(self, out):
        self.state_dict['last_output'] = out
        for cb in self.callbacks:
            a = cb.on_loss_begin(**self.state_dict)
            if a is not None: self.state_dict['last_output'] = a
        return self.state_dict['last_output']
    
    def on_backward_begin(self, loss):
        self.smoothener.add_value(loss.item())
        self.state_dict['last_loss'], self.state_dict['smooth_loss'] = loss, self.smoothener.smooth
        for cb in self.callbacks:
            a = cb.on_backward_begin(**self.state_dict)
            if a is not None: self.state_dict['last_loss'] = a
        return self.state_dict['last_loss']
    
    def on_backward_end(self):        self('backward_end')
    def on_step_end(self):            self('step_end')
        
    def on_batch_end(self, loss):     
        self.state_dict['last_loss'] = loss
        stop = np.any(self('batch_end'))
        self.state_dict['iteration'] += 1
        self.state_dict['num_batch'] += 1
        return stop
    
    def on_epoch_end(self, val_metrics):
        self.state_dict['last_metrics'] = val_metrics
        stop = np.any(self('epoch_end'))
        self.state_dict['epoch'] += 1
        return stop
    
    def on_train_end(self): self('train_end')

def loss_batch(model, xb, yb, loss_fn, opt=None, cb_handler=None, metrics=None):
    if cb_handler is None: cb_handler = CallbackHandler([])
    out = model(xb)
    out = cb_handler.on_loss_begin(out)
    loss = loss_fn(out, yb)
    mets = [f(out,yb).item() for f in metrics] if metrics is not None else []
    
    if opt is not None:
        loss = cb_handler.on_backward_begin(loss)
        loss.backward()
        cb_handler.on_backward_end()
        opt.step()
        cb_handler.on_step_end()
        opt.zero_grad()
        
    return (loss.item(),) + tuple(mets) + (len(xb),)

def fit(epochs, model, loss_fn, opt, data, callbacks=None, metrics=None):
    cb_handler = CallbackHandler(callbacks)
    cb_handler.on_train_begin()
    
    for epoch in tnrange(epochs):
        model.train()
        cb_handler.on_epoch_begin()
        
        for xb,yb in data.train_dl:
            xb, yb = cb_handler.on_batch_begin(xb, yb)
            loss,_ = loss_batch(model, xb, yb, loss_fn, opt, cb_handler)
            if cb_handler.on_batch_end(loss): break
        
        if hasattr(data,'valid_dl') and data.valid_dl is not None:
            model.eval()
            with torch.no_grad():
                *val_metrics,nums = zip(*[loss_batch(model, xb, yb, loss_fn, cb_handler=cb_handler, metrics=metrics)
                                for xb,yb in data.valid_dl])
            val_metrics = [np.sum(np.multiply(val,nums)) / np.sum(nums) for val in val_metrics]
            
        else: val_metrics=None
        if cb_handler.on_epoch_end(val_metrics): break
        
    cb_handler.on_train_end()

def accuracy(out, yb):
    preds = torch.max(out, dim=1)[1]
    return (preds==yb).float().mean()

def annealing_no(start, end, pct): return start
def annealing_linear(start, end, pct): return start + pct * (end-start)
def annealing_exp(start, end, pct): return start * (end/start) ** pct
def annealing_cos(start, end, pct):
    cos_out = np.cos(np.pi * pct) + 1
    return end + (start-end)/2 * cos_out
    
def do_annealing_poly(start, end, pct, degree): return end + (start-end) * (1-pct)**degree
def annealing_poly(degree): return functools.partial(do_annealing_poly, degree=degree)

def is_tuple(x): return isinstance(x, tuple)

class Stepper():
    def __init__(self, vals, num_it, ft=None):
        self.start,self.end = (vals[0],vals[1]) if is_tuple(vals) else (vals,0)
        self.num_it = num_it
        if ft is None: self.ft = annealing_linear if is_tuple(vals) else annealing_no
        else:          self.ft = ft
        self.n = 0
    
    def step(self):
        self.n += 1
        return self.ft(self.start, self.end, self.n/self.num_it)
    
    @property
    def is_done(self):  return self.n >= self.num_it

class OneCycleScheduler(Callback):
    def __init__(self, learn, lr_max, epochs, moms=(0.95,0.85), div_factor=10, pct_end=0.1):
        self.learn = learn
        a = int(len(learn.data.train_dl) * epochs * (1 - pct_end) / 2)
        b = int(len(learn.data.train_dl) * epochs * pct_end)
        self.lr_scheds = [Stepper((lr_max/div_factor, lr_max), a),
                          Stepper((lr_max, lr_max/div_factor), a),
                          Stepper((lr_max/div_factor, lr_max/(div_factor*100)), b)]
        self.mom_scheds = [Stepper(moms, a), Stepper((moms[1], moms[0]), a), Stepper(moms[0], b)]
    
    def on_train_begin(self, **kwargs):
        self.opt = self.learn.opt
        self.opt.lr, self.opt.mom = self.lr_scheds[0].start, self.mom_scheds[0].start
        self.idx_s = 0
    
    def on_batch_end(self, **kwargs):
        self.opt.lr = self.lr_scheds[self.idx_s].step()
        self.opt.mom = self.mom_scheds[self.idx_s].step()
        if self.lr_scheds[self.idx_s].is_done:
            self.idx_s += 1
            if self.idx_s >= len(self.lr_scheds): return True

@dataclass
class Learner():
    data: DataBunch
    model: nn.Module
    opt_fn: Callable = optim.SGD
#     loss_fn: LossType = F.cross_entropy
    loss_fn: Callable = F.cross_entropy
    metrics: Collection[Callable] = None
    true_wd: bool = False
    def __post_init__(self): self.model = self.model.to(self.data.device)

    def fit(self, epochs, lr, wd=0., callbacks=None):
        if not hasattr(self, 'opt'): self.create_opt(lr, wd)
        self.recorder = Recorder(self.opt, self.data.train_dl)
        if callbacks is None: callbacks = []
        callbacks = [self.recorder]+callbacks
        fit(epochs, self.model, self.loss_fn, self.opt, self.data, callbacks=callbacks, metrics=self.metrics)
    
    def create_opt(self, lr, wd=0.):
        self.opt = OptimWrapper(self.opt_fn(self.model.parameters(), lr), wd=wd, true_wd=self.true_wd)

class LRFinder(Callback):
    def __init__(self, opt, data, start_lr=1e-5, end_lr=10, num_it=200):
        self.opt,self.data = opt,data
        self.sched = Stepper((start_lr, end_lr), num_it, annealing_exp)
        #To avoid validating if the train_dl has less than num_it batches, we put aside the valid_dl and remove it
        #during the call to fit.
        self.valid_dl = data.valid_dl
        self.data.valid_dl = None
    
    def on_train_begin(self, **kwargs):
        self.opt.lr = self.sched.start
        self.stop,self.best_loss = False,0.
    
    def on_batch_end(self, iteration, smooth_loss, **kwargs):
        if iteration==0 or smooth_loss < self.best_loss: self.best_loss = smooth_loss
        self.opt.lr = self.sched.step()
        if self.sched.is_done or smooth_loss > 4*self.best_loss:
            #We use the smoothed loss to decide on the stopping since it's less shaky.
            self.stop=True
            return True
    
    def on_epoch_end(self, **kwargs): return self.stop
    
    def on_train_end(self, **kwargs):
        #Clean up and put back the valid_dl in its place.
        self.data.valid_dl = self.valid_dl

def lr_find(learn, start_lr=1e-5, end_lr=10, num_it=100):
    #TODO: add model.save and model.load.
    learn.create_opt(start_lr)
    cb = LRFinder(learn.opt, learn.data, start_lr, end_lr, num_it)
    a = int(np.ceil(num_it/len(learn.data.train_dl)))
    learn.fit(a, start_lr, callbacks=[cb])

@dataclass
class Recorder(Callback):
    opt: torch.optim
    train_dl: DeviceDataLoader = None

    def on_train_begin(self, **kwargs):
        self.losses,self.val_losses,self.lrs,self.moms,self.metrics,self.nb_batches = [],[],[],[],[],[]
    
    def on_batch_begin(self, **kwargs):
        self.lrs.append(self.opt.lr)
        self.moms.append(self.opt.mom)
    
    def on_backward_begin(self, smooth_loss, **kwargs):
        #We record the loss here before any other callback has a chance to modify it.
        self.losses.append(smooth_loss)
        if self.train_dl is not None and self.train_dl.progress_func is not None: 
            self.train_dl.gen.set_postfix_str(smooth_loss)
    
    def on_epoch_end(self, epoch, num_batch, smooth_loss, last_metrics, **kwargs):
        self.nb_batches.append(num_batch)
        if last_metrics is not None:
            self.val_losses.append(last_metrics[0])
            if len(last_metrics) > 1: self.metrics.append(last_metrics[1:])
            print(epoch, smooth_loss, *last_metrics)
        else:  print(epoch, smooth_loss)
    
    def plot_lr(self, show_moms=False):
        iterations = list(range(len(self.lrs)))
        if show_moms:
            _, axs = plt.subplots(1,2, figsize=(12,4))
            axs[0].plot(iterations, self.lrs)
            axs[1].plot(iterations, self.moms)
        else: plt.plot(iterations, self.lrs)
    
    def plot(self, skip_start=10, skip_end=5):
        lrs = self.lrs[skip_start:-skip_end] if skip_end > 0 else self.lrs[skip_start:]
        losses = self.losses[skip_start:-skip_end] if skip_end > 0 else self.losses[skip_start:]
        _, ax = plt.subplots(1,1)
        ax.plot(lrs, losses)
        ax.set_xscale('log')
    
    def plot_losses(self):
        _, ax = plt.subplots(1,1)
        iterations = list(range(len(self.losses)))
        ax.plot(iterations, self.losses)
        val_iter = self.nb_batches
        val_iter = np.cumsum(val_iter)
        ax.plot(val_iter, self.val_losses)
    
    def plot_metrics(self):
        assert len(self.metrics) != 0, "There is no metrics to plot."
        _, axes = plt.subplots(len(self.metrics[0]),1,figsize=(6, 4*len(self.metrics[0])))
        val_iter = self.nb_batches
        val_iter = np.cumsum(val_iter)
        axes = axes.flatten() if len(self.metrics[0]) != 1 else [axes]
        for i, ax in enumerate(axes):
            values = [met[i] for met in self.metrics]
            ax.plot(val_iter, values)