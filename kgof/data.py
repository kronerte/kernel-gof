"""
Module containing data structures for representing datasets.
"""

__author__ = 'wittawat'

from abc import ABCMeta, abstractmethod
import math
import autograd.numpy as np
import kgof.util as util
import scipy.stats as stats

class Data(object):
    """
    Class representing a dataset i.e., en encapsulation of a data matrix 
    whose rows are vectors drawn from a distribution.
    """

    def __init__(self, X):
        """
        :param X: n x d numpy array for dataset X
        """
        self.X = X

        if not np.all(np.isfinite(X)):
            print 'X:'
            print util.fullprint(X)
            raise ValueError('Not all elements in X are finite.')

    def __str__(self):
        mean_x = np.mean(self.X, 0)
        std_x = np.std(self.X, 0) 
        prec = 4
        desc = ''
        desc += 'E[x] = %s \n'%(np.array_str(mean_x, precision=prec ) )
        desc += 'Std[x] = %s \n' %(np.array_str(std_x, precision=prec))
        return desc

    def dim(self):
        """Return the dimension of the data."""
        dx = self.X.shape[1]
        return dx

    def sample_size(self):
        return self.X.shape[0]

    def n(self):
        return self.sample_size()

    def data(self):
        """Return the data matrix."""
        return self.X

    def split_tr_te(self, tr_proportion=0.5, seed=820):
        """Split the dataset into training and test sets.         

        Return (Data for tr, Data for te)"""
        X = self.X
        nx, dx = X.shape
        Itr, Ite = util.tr_te_indices(nx, tr_proportion, seed)
        tr_data = Data(X[Itr, :])
        te_data = Data(X[Ite, :])
        return (tr_data, te_data)

    def subsample(self, n, seed=87):
        """Subsample without replacement. Return a new Data. """
        if n > self.X.shape[0]:
            raise ValueError('n should not be larger than sizes of X')
        ind_x = util.subsample_ind( self.X.shape[0], n, seed )
        return Data(self.X[ind_x, :])

    def clone(self):
        """
        Return a new Data object with a separate copy of each internal 
        variable, and with the same content.
        """
        nX = np.copy(self.X)
        return Data(nX)

    def __add__(self, data2):
        """
        Merge the current Data with another one.
        Create a new Data and create a new copy for all internal variables.
        """
        copy = self.clone()
        copy2 = data2.clone()
        nX = np.vstack((copy.X, copy2.X))
        return Data(nX)

### end Data class        


class DataSource(object):
    """
    A source of data allowing resampling. Subclasses may prefix 
    class names with DS. 
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def sample(self, n, seed):
        """Return a Data. Returned result should be deterministic given 
        the input (n, seed)."""
        raise NotImplementedError()

    #@abstractmethod
    #def dim(self):
    #    """Return the dimension of the data. """
    #    raise NotImplementedError()

#  end DataSource

class DSIsotropicNormal(DataSource):
    """
    A DataSource providing samples from a mulivariate isotropic normal
    distribution.
    """
    def __init__(self, mean, variance):
        """
        mean: a numpy array of length d for the mean 
        variance: a positive floating-point number for the variance.
        """
        assert len(mean.shape) == 1
        self.mean = mean 
        self.variance = variance

    def sample(self, n, seed=2):
        with util.NumpySeedContext(seed=seed):
            d = len(self.mean)
            mean = self.mean
            variance = self.variance
            X = np.random.randn(n, d)*np.sqrt(variance) + mean
            return Data(X)


class DSNormal(DataSource):
    """
    A DataSource implementing a multivariate Gaussian.
    """
    def __init__(self, mean, cov):
        """
        mean: a numpy array of length d.
        cov: d x d numpy array for the covariance.
        """
        self.mean = mean 
        self.cov = cov
        assert mean.shape[0] == cov.shape[0]
        assert cov.shape[0] == cov.shape[1]

    def sample(self, n, seed=3):
        with util.NumpySeedContext(seed=seed):
            mvn = stats.multivariate_normal(self.mean, self.cov)
            X = mvn.rvs(size=n)
            if len(X.shape) ==1:
                # This can happen if d=1
                X = X[:, np.newaxis]
            return Data(X)

class DSLaplace(DataSource):
    """
    A DataSource for a multivariate Laplace distribution.
    """
    def __init__(self, d, loc=0, scale=1):
        """
        loc: location 
        scale: scale parameter.
        Described in https://docs.scipy.org/doc/numpy/reference/generated/numpy.random.laplace.html#numpy.random.laplace
        """
        assert d > 0
        self.d = d
        self.loc = loc
        self.scale = scale

    def sample(self, n, seed=4):
        with util.NumpySeedContext(seed=seed):
            X = np.random.laplace(loc=self.loc, scale=self.scale, size=(n, self.d))
            return Data(X)

class DSTDistribution(DataSource):
    """
    A DataSource for a univariate T-distribution.
    """
    def __init__(self, df):
        """
        df: degrees of freedom
        """
        assert df > 0
        self.df = df 

    def sample(self, n, seed=5):
        with util.NumpySeedContext(seed=seed):
            X = stats.t.rvs(df=self.df, size=n)
            X = X[:, np.newaxis]
            return Data(X)

# end class DSTDistribution


class DSGaussBernRBM(DataSource):
    """
    A DataSource implementing a Gaussian-Bernoulli Restricted Boltzmann Machine.
    The probability of the latent vector h is controlled by the vector c.
    The parameterization of the Gaussian-Bernoulli RBM is given in 
    density.GaussBernRBM.

    - It turns out that this is equivalent to drawing a vector of {-1, 1} for h
        according to h ~ Discrete(sigmoid(2c)).
    - Draw x | h ~ N(B*h+b, I)
    """
    def __init__(self, B, b, c, burnin=50):
        """
        B: a dx x dh matrix 
        b: a numpy array of length dx
        c: a numpy array of length dh
        burnin: burn-in iterations when doing Gibbs sampling
        """
        assert burnin >= 0
        dh = len(c)
        dx = len(b)
        assert B.shape[0] == dx
        assert B.shape[1] == dh
        assert dx > 0
        assert dh > 0
        self.B = B
        self.b = b
        self.c = c
        self.burnin = burnin

    @staticmethod
    def sigmoid(x):
        """
        x: a numpy array.
        """
        return 1.0/(1+np.exp(-x))

    def _blocked_gibbs_next(self, X, H):
        """
        Sample from the mutual conditional distributions.
        """
        dh = H.shape[1]
        n, dx = X.shape
        B = self.B
        b = self.b

        # Draw H.
        XBC = np.dot(X, self.B) + self.c
        # Ph: n x dh matrix
        Ph = DSGaussBernRBM.sigmoid(2*XBC)
        # H: n x dh
        # Don't know how to make this faster.
        H = np.zeros((n, dh))
        for i in range(n):
            for j in range(dh):
                H[i, j] = stats.bernoulli.rvs(p=Ph[i, j], size=1)*2 - 1.0
        assert np.all(np.abs(H) - 1 <= 1e-6 )
        # Draw X.
        # mean: n x dx
        mean = np.dot(H, B.T) + b
        X = np.random.randn(n, dx) + mean
        return X, H

    def sample(self, n, seed=3, return_latent=False):
        """
        Sample by blocked Gibbs sampling
        """
        B = self.B
        b = self.b
        c = self.c
        dh = len(c)
        dx = len(b)

        # Initialize the state of the Markov chain
        with util.NumpySeedContext(seed=seed):
            X = np.random.randn(n, dx)
            H = np.random.randint(1, 2, (n, dh))*2 - 1.0
        # burn-in
        for t in range(self.burnin):
            X, H = self._blocked_gibbs_next(X, H)
        # sampling
        X, H = self._blocked_gibbs_next(X, H)
        if return_latent:
            return Data(X), H
        else:
            return Data(X)
# end class DSGaussBernRBM

class DSNonHomPoissonLinear(DataSource):
    """
    A DataSource implementing non homogenous poisson process.
    """
    def __init__(self, b):
        """
        b: slope in of the linear function
        lambda_X = 1 + bX
        """
        if b < 0:
            raise ValueError('Parameter b must be non-negative.')
        self.b = b
    
    def nonhom_linear(self,size):
        b = self.b
        u = np.random.rand(size)
        if np.abs(b) <= 1e-8:
            F_l = -np.log(1-u)
        else:
            F_l = np.sqrt(-2.0/b*np.log(1-u)+1.0/(b**2))-1.0/b
        return F_l
        
    def sample(self, n, seed=3):
        with util.NumpySeedContext(seed=seed):
            X = self.nonhom_linear(size=n)
            if len(X.shape) ==1:
                # This can happen if d=1
                X = X[:, np.newaxis]
            return Data(X)

# end class DSNonHomPoissonLinear

class DSNonHomPoissonSine(DataSource):
    """
    A DataSource implementing non homogenous poisson process with sine intensity.
    lambda = b*(1+sin(w*X))
    """
    def __init__(self, w, b, delta=0.001):
        """
        w: the frequency of sine function
        b: amplitude of intensity function
        """
        self.b = b
        self.w = w
        self.delta = delta
        
    def func(self,t):
        val = (t + (1-np.cos(self.w*t))/self.w )*self.b
        return val
    
    # slow step-by-step increment by assigned delta
    def find_time(self, x):
        t = 0.0
        while self.func(t) < x:
            t += self.delta
        return t

    # bisection search to find t value with accuracy delta
    def search_time(self, x):
        b = self.b
        w = self.w
        delta = self.delta
        t_old = 0.0
        t_new = b
        val_old = self.func(t_old)
        val_new = self.func(t_new)
        while np.abs(val_new-x) > delta:
            if val_new < x and t_old < t_new:
                t_old = t_new
                t_new = t_new * 2.0
                val_old = val_new
                val_new = self.func(t_new)
            elif val_new < x and t_old > t_new:
                temp = (t_old + t_new) / 2.0
                t_old = t_new
                t_new = temp
                val_old = val_new
                val_new = self.func(t_new)
            elif val_new > x and t_old > t_new:
                t_old = t_new
                t_new = t_new / 2.0
                val_old = val_new
                val_new = self.func(t_new)
            elif val_new > x and t_old < t_new:
                temp = (t_old + t_new) / 2.0
                t_old = t_new
                t_new = temp
                val_old = val_new
                val_new = self.func(t_new)
        t = t_new
        return t
        
    def nonhom_sine(self,size=1000):
        u = np.random.rand(size)
        x = -np.log(1-u)
        t = np.zeros(size)
        for i in range(size):
            t[i] = self.search_time(x[i])
        return t

    def sample(self, n, seed=3):
        with util.NumpySeedContext(seed=seed):
            X = self.nonhom_sine(size=n)
            if len(X.shape) ==1:
                # This can happen if d=1
                X = X[:, np.newaxis]
            return Data(X)

# end class DSNonHomPoissonSine


class DSGamma(DataSource):
    """
    A DataSource implementing gamma distribution.
    """
    def __init__(self, alpha, beta=1.0):
        """
        alpha: shape of parameter
        beta: scale
        """
        self.alpha = alpha
        self.beta = beta

    def sample(self, n, seed=3):
        with util.NumpySeedContext(seed=seed):
            X = stats.gamma.rvs(self.alpha, size=n, scale = 1.0/self.beta)
            if len(X.shape) ==1:
                # This can happen if d=1
                X = X[:, np.newaxis]
            return Data(X)

# end class DSGamma


class DSLogGamma(DataSource):
    """
    A DataSource implementing the transformed gamma distribution.
    """
    def __init__(self, alpha, beta=1.0):
        """
        alpha: shape of parameter
        beta: scale
        """
        self.alpha = alpha
        self.beta = beta

    def sample(self, n, seed=3):
        with util.NumpySeedContext(seed=seed):
            X = np.log(stats.gamma.rvs(self.alpha, size=n, scale = 1.0/self.beta))
            if len(X.shape) ==1:
                # This can happen if d=1
                X = X[:, np.newaxis]
            return Data(X)

# end class DSGamma

class DSLogPoissonLinear(DataSource):
    """
    A DataSource implementing non homogenous poisson process.
    """
    def __init__(self, b):
        """
        b: slope in of the linear function
        lambda_X = 1 + bX
        """
        if b < 0:
            raise ValueError('Parameter b must be non-negative.')
        self.b = b
    
    def nonhom_linear(self,size):
        b = self.b
        u = np.random.rand(size)
        if np.abs(b) <= 1e-8:
            F_l = -np.log(1-u)
        else:
            F_l = np.sqrt(-2.0/b*np.log(1-u)+1.0/(b**2))-1.0/b
        return F_l
        
    def sample(self, n, seed=3):
        with util.NumpySeedContext(seed=seed):
            X = np.log(self.nonhom_linear(size=n))
            if len(X.shape) ==1:
                # This can happen if d=1
                X = X[:, np.newaxis]
            return Data(X)

# end class DSLogPoissonLinear

class DSPoisson2D(DataSource):
    """
     A DataSource implementing non homogenous poisson process.
    """
    def __init__(self):
        """
        lambda_(X,Y) = X^2 + Y^2
        lamb_bar: upper-bound used in rejection sampling
        """

    def quadratic_intensity(self, X):
        intensity = self.lamb_bar*np.sum(X**2,1)
        return intensity


    def inh2d(self, lamb_bar = 100000):
        self.lamb_bar = lamb_bar
        N = np.random.poisson(2*self.lamb_bar)
        X = np.random.rand(N,2)
        intensity = self.quadratic_intensity(X)
        u = np.random.rand(N)
        lamb_T = intensity/lamb_bar
        X_acc = X[u < lamb_T]
        return X_acc

    def sample(self, n, seed=3):
        with util.NumpySeedContext(seed=seed):
            X = self.inh2d(lamb_bar=n)
            if len(X.shape) ==1:
                # This can happen if d=1
                X = X[:, np.newaxis]
            return Data(X)

# end class DSPoisson2D

class DSSigmoidPoisson2D(DataSource):
    """
     A DataSource implementing non homogenous poisson process.
    """
    def __init__(self, a=1.0):
        """
        lambda_(X,Y) = a*X^2 + Y^2
        X = 1/(1+exp(s))
        Y = 1/(1+exp(t))
        X, Y \in [0,1], s,t \in R
        """
        self.a = a

    def quadratic_intensity(self, X):
        intensity = self.lamb_bar*np.average(X**2, axis=1, weights=[self.a,1])
        return intensity


    def inh2d(self, lamb_bar = 100000):
        self.lamb_bar = lamb_bar
        N = np.random.poisson(2*self.lamb_bar)
        X = np.random.rand(N,2)
        intensity = self.quadratic_intensity(X)
        u = np.random.rand(N)
        lamb_T = intensity/lamb_bar
        X_acc = X[u < lamb_T]
        return X_acc

    def sample(self, n, seed=3):
        with util.NumpySeedContext(seed=seed):
            X = np.log(1/self.inh2d(lamb_bar=n)-1)
            if len(X.shape) ==1:
                # This can happen if d=1
                X = X[:, np.newaxis]
            return Data(X)

# end class DSSigmoidPoisson2D