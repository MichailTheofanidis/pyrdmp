'''
    Dynamic Movement Primitive Class
    Author: Michail Theofanidis, Joe Cloud, James Brady
'''

import numpy as np
from pyrdmp.utils import psi

class DynamicMovementPrimitive:

    """Create an DMP.
        
        Keyword arguments:
        a -- Gain a of the transformation system
        b -- Gain b of the transformation system
        as_deg -- Degradation of the canonical system
        ng -- Number of Gaussian
        stb -- Stabilization term
    """

    def __init__(self, _a, _ng, _stb):
       
        self.a = _a
        self.b = self.a/4
        self.as_deg = self.a/3
        self.ng = _ng
        self.stb = _stb

    # Create the phase of the system using the time vector
    def phase(self, time):
        return np.exp((-self.as_deg) * np.linspace(0, 1.0, len(time))).T

    # Generate a gaussian distribution
    def distributions(self, s):

        # Find the centers of the Gaussian in the s domain
        step = np.divide(s[0]-s[-1], self.ng-1)
        c = np.arange(min(s), max(s)+step, step)
        d = np.diff(c)
        c = np.divide(c, d[0])

        # Calculate every gaussian
        h = 1
        psv = np.zeros((self.ng, len(s)))

        for i in range(0, self.ng):
            for j in range(0, len(s)):
                psv[i][j] = psi(h, c[i], np.divide(s[j], d[0]))

        return psv

    # Imitation Learning
    def imitate(self, x, dx, ddx, time, s, psv):

        # Initialize variables
        sigma = np.zeros(len(time))
        f_target = np.zeros(len(time))
        w = np.zeros(self.ng)

        g = x[-1]
        x0 = x[0]
        tau = time[-1]

        # Compute ftarget
        for i in range(0, len(time)):

            # Add stabilization term
            if self.stb == 1:
                mod = np.multiply(self.b*(g-x0), s[i])
                sigma[i] = np.multiply(g-x0, s[i])
            else:
                mod = 0
                sigma[i] = s[i]

            # Check again in the future
            f_target[i] = np.multiply(np.power(tau, 2), ddx[i]) - self.a*(self.b*(g-x[i])-tau*dx[i])+mod

        # Regression
        for i in range(0, self.ng):

            w[i] = np.divide(np.matmul(np.matmul(sigma.T, np.diag(psv[i, :])), f_target), np.matmul(np.matmul(sigma.T, np.diag(psv[i, :])), sigma))

        return f_target, w

    # Generate a trajectory
    def generate(self, w, x0, g, time, s, psv):

        # Initialize variables
        ddx = np.zeros(len(time))
        dx = np.zeros(len(time))
        x = np.zeros(len(time))
        sigma = np.zeros(len(time))
        f_rep = np.zeros(len(time))

        tau = time[-1]

        dx_r = 0
        x_r = x0

        for i in range(0, len(time)):

            p_sum = 0
            p_div = 0

            if i == 0:
                dt = time[i]
            else:
                dt = time[i] - time[i - 1]

            # Add stabilization term
            if self.stb == 1:
                mod = np.multiply(self.b*(g-x0), s[i])
                sigma[i] = np.multiply(g-x0, s[i])
            else:
                mod = 0
                sigma[i] = s[i]

            for j in range(0, self.ng):

                p_sum = p_sum + np.multiply(psv[j][i], w[j])
                p_div = p_div + psv[j][i]

            # Calculate the new control input
            f_rep[i] = np.multiply(np.divide(p_sum, p_div), sigma[i])

            # Calculate the new trajectory
            ddx_r = np.divide(self.a*(self.b*(g-x_r)-tau*dx_r)+f_rep[i]+mod, np.power(tau, 2))
            dx_r = dx_r + np.multiply(ddx_r, dt)
            x_r = x_r + np.multiply(dx_r, dt)

            ddx[i] = ddx_r
            dx[i] = dx_r
            x[i] = x_r

        return ddx, dx, x

    # Adaptation using reinforcement learning
    def adapt(self, w, x0, g, t, s, psv, samples, rate):

        # Initialize the action variables
        actions = np.zeros((samples, self.ng))
        exploration = np.zeros((samples, self.ng))
        a = w
        tau = t[-1]

        # Flag which acts as a stop condition
        flag = 0

        while flag == 0:

            for i in range(0, samples):
                for j in range(0, self.ng):
                    exploration[i, j] = np.random.normal(0, np.std(psv[j, :]*a[j]))

            for i in range(0, samples):
                actions[i, :] = a + exploration[i, :]

            # Generate new rollouts
            x = np.zeros((len(t), samples))
            dx = np.zeros((len(t), samples))
            ddx = np.zeros((len(t), samples))

            for i in range(0, samples):
                ddx[:, i], dx[:, i], x[:, i] = self.generate(actions[i, :], x0, g, t, s, psv)

            # Estimate the Q values
            Q = np.zeros(samples)

            for i in range(0, samples):
                sum = 0
                for j in range(0, len(t)):
                    sum = sum + self.reward(g, x[j, i], t[j], tau)
                Q[i] = sum

            # Sample the highest Q values to adapt the action parameters
            sorted_samples = np.argsort(Q)[::-1][:np.floor(samples*rate).astype(int)]

            # Update the action parameter
            sumQ_y = 0
            sumQ_x = np.zeros(a.shape)

            for i in sorted_samples:
                sumQ_y = sumQ_y + Q[i]
                sumQ_x = sumQ_x + exploration[i, :]*Q[i]

            a = a + sumQ_x/sumQ_y

            if np.abs(x[-1, sorted_samples[0]])-g < 0.1:
                flag = 1

        return ddx[:, sorted_samples[0]], dx[:, sorted_samples[0]], x[:, sorted_samples[0]]

    # Reward function
    def reward(self, goal, position, time, tau):

        w = 0.5
        thres = 0.01
        temp = goal - position

        if np.abs(time - tau) < thres:
            rwd = w*np.exp(-np.abs(np.power(temp, 2)))
        else:
            rwd = (1-w) * np.exp(-np.abs(np.power(temp, 2)))/tau

        return rwd

