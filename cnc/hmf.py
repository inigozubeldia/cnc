import numpy as np
import pylab as pl
import copy
from mcfit import TophatVar
import time

class halo_mass_function:

    def __init__(self,
                 cosmology=None,
                 hmf_type="Tinker08",
                 mass_definition="500c",
                 M_min=1e13,M_max=1e16,
                 n_points=1000,
                 type_deriv="numerical",
                 hmf_calc="cnc",
                 extra_params=None):

        self.hmf_type = hmf_type
        self.mass_definition = mass_definition
        self.cosmology = cosmology
        self.h = self.cosmology.background_cosmology.H0.value/100.

        self.M_min = M_min
        self.M_max = M_max
        self.n_points = n_points
        self.type_deriv = type_deriv
        self.hmf_calc = hmf_calc
        self.extra_params = extra_params

        self.const = constants()

        # do class_sz stuff
        # M = Class()
        # M.set(common_params)
        # M.set(cosmo_params_comparison)
        # M.set(szcounts_param)
        # # M.set({'output':''})
        # M.compute_class_szfast()
        # self.classy_sz_object = M

        if self.hmf_type == "Tinker08":

            self.rho_c_0 = self.cosmology.background_cosmology.critical_density(0.).value*self.const.mpc**3/self.const.solar*1e3

        if self.hmf_calc == "hmf":

            import hmf as hmf_package

            if self.mass_definition[-1] == "c":

                md = "SOCritical"

            elif self.mass_definition[-1] == "m":

                md = "SOMean"

            self.massfunc_hmf = hmf_package.MassFunction(Mmax=np.log10(self.M_max*self.h),
                                                         Mmin=np.log10(self.M_min*self.h),
                                                         z=0.,
                                                         mdef_model=md,
                                                         mdef_params={"overdensity":float(self.mass_definition[0:-1])},
                                                         cosmo_model=self.cosmology.background_cosmology,
                                                         dlog10m=0.005,
                                                         sigma_8=cosmology.cosmo_params["sigma_8"],
                                                         n=cosmology.cosmo_params["n_s"])

    def eval_hmf(self,redshift,log=False,volume_element=False):

        if log == False:

            M_vec = np.linspace(self.M_min,self.M_max,self.n_points)

        elif log == True:

            M_vec = np.exp(np.linspace(np.log(self.M_min),np.log(self.M_max),self.n_points))

        if self.hmf_calc == "cnc":

            if self.hmf_type == "Tinker08":
                k,ps = self.cosmology.power_spectrum.get_linear_power_spectrum(redshift)

                rho_m = self.rho_c_0*self.cosmology.cosmo_params["Om0"]

                sigma_r = sigma_R((k,ps),cosmology=self.cosmology)
                sigma_r.get_derivative(type_deriv=self.type_deriv)
                (sigma,dsigmadR) = sigma_r.get_sigma_M(M_vec,rho_m,get_deriv=True)

                self.sigma = sigma
                self.dsigmadR = dsigmadR
                self.R = sigma_r.R_eval

                dMdR = 4.*np.pi*rho_m*self.R**2

                if self.mass_definition[-1] == "c":

                    rescale = self.cosmology.cosmo_params["Om0"]*(1.+redshift)**3/(self.cosmology.background_cosmology.H(redshift).value/(self.cosmology.cosmo_params["h"]*100.))**2

                elif self.mass_definition[-1] == "m":

                    rescale = 1

                Delta = float(self.mass_definition[0:-1])/rescale

                fsigma = f_sigma(sigma,redshift=redshift,hmf_type=self.hmf_type,Delta=Delta,mass_definition=self.mass_definition)
                self.fsigma = fsigma

                hmf = -fsigma*rho_m/M_vec/dMdR*dsigmadR/sigma
                M_eval = M_vec

                hmf = hmf*1e14
                M_eval = M_eval/1e14

                if log == True:

                    hmf = hmf*M_eval
                    M_eval = np.log(M_eval)

        elif self.hmf_calc == "hmf":

            self.massfunc_hmf.update(z=redshift)
            hmf = self.massfunc_hmf.dndm*1e14*self.h**4
            M_eval = self.massfunc_hmf.m/self.h/1e14

            hmf = np.interp(M_vec/1e14,M_eval,hmf)
            M_eval = M_vec/1e14

            if log == True:

                hmf = hmf*M_eval
                M_eval = np.log(M_eval)

        elif self.hmf_calc == "MiraTitan": #only works if log == True, note that returns a matrix instead of a vector

            t0 = time.time()

            if log == True:

                MT_emulator = self.extra_params["emulator"]

                M_vec = np.linspace(self.M_min,self.M_max,self.n_points)

                cosmology_emulator = {
                "h": self.h,
                "Ommh2": self.cosmology.cosmo_params["Om0"]*self.h**2,
                "Ombh2": self.cosmology.cosmo_params["Ob0"]*self.h**2,
                "Omnuh2": self.cosmology.background_cosmology.Onu0*self.h**2,
                "sigma_8": self.cosmology.cosmo_params["sigma_8"],
                "n_s": self.cosmology.cosmo_params["n_s"],
                "w_0": -1.,
                "w_a": 0.
                }

                hmf = np.array(MT_emulator.predict(cosmology_emulator,redshift,M_vec*self.h))[0,:,:]*self.h**3/np.log(10.)
                M_eval = np.log(M_vec/1e14)

                if volume_element == True:

                    for i in range(0,hmf.shape[0]):

                        hmf[i,:] = hmf[i,:]*self.cosmology.background_cosmology.differential_comoving_volume(redshift[i]).value

        if volume_element == True and self.hmf_calc != "MiraTitan":


            # print('hmf at z ',redshift)
            # print(hmf[:10],np.exp(M_eval[:10])*1e14)
            # print(np.shape(hmf),np.shape(M_eval))
            # hmf_class = np.vectorize(self.classy_sz_object.get_dndlnM_at_z_and_M)(redshift,np.exp(M_eval)*1e14*hparam)
            # hmf_class *= hparam**3
            # # print('hmfclass:',hmf_class[:10])
            # hmf = hmf_class
            # vol = self.cosmology.background_cosmology.differential_comoving_volume(redshift).value
            # print('vol:',vol,redshift)
            # exit(0)
            hmf = hmf*self.cosmology.background_cosmology.differential_comoving_volume(redshift).value

        # exit(0)

        return M_eval,hmf

class sigma_R:

    def __init__(self,ps,cosmology=None,deriv=0):

        self.cosmology = cosmology
        (self.k,self.pk) = ps

        self.R_vec,self.var_vec = TophatVar(self.k,lowring=True,deriv=0)(self.pk,extrap=True)
        self.sigma_vec = np.sqrt(self.var_vec)

    def get_derivative(self,type_deriv="analytical"):

        if type_deriv == "analytical":

            R_vec,self.dvar = TophatVar(self.k,lowring=True,deriv=1)(self.pk*self.k,extrap=True)
            self.dsigma_vec = self.dvar/(2.*self.sigma_vec)

        elif type_deriv == "numerical":

            self.dsigma_vec = np.gradient(self.sigma_vec,self.R_vec)

    def get_sigma_M(self,M_vec,rho_m,get_deriv=False):

        R = (3.*M_vec/(4.*np.pi*rho_m))**(1./3.)
        self.R_eval = R

        sigma = np.interp(R,self.R_vec,self.sigma_vec)

        if get_deriv == False:

            ret = sigma

        elif get_deriv == True:

            dsigmadR = np.interp(R,self.R_vec,self.dsigma_vec)
            ret = (sigma,dsigmadR)

        return ret

#Delta is w.r.t. mean

def f_sigma(sigma,redshift=None,hmf_type="Tinker08",Delta=None,mass_definition="500c"):

    params = hmf_params(hmf_type=hmf_type,mass_definition=mass_definition)

    if hmf_type == "Tinker08":

        alpha = 10.**(-(0.75/np.log10(Delta/75.))**1.2)

        A = params.get_param("A",Delta)*(1.+redshift)**(-0.14)
        a = params.get_param("a",Delta)*(1.+redshift)**(-0.06)
        b = params.get_param("b",Delta)*(1.+redshift)**(-alpha)
        c = params.get_param("c",Delta)

        f = A*((sigma/b)**(-a)+1.)*np.exp(-c/sigma**2)

    return f

class hmf_params:

    def __init__(self,hmf_type="Tinker08",mass_definition="500c"):

        self.hmf_type = hmf_type
        self.mass_definition = mass_definition

        if self.hmf_type == "Tinker08":

            if self.mass_definition == "500c":

                Delta = np.array([200.,300.,400.,600.,800.,1200.,1600.,2400.,3200.])
                A = np.array([0.186,0.2,0.212,0.218,0.248,0.255,0.260,0.260,0.260])
                a = np.array([1.47,1.52,1.56,1.61,1.87,2.13,2.30,2.53,2.66])
                b = np.array([2.57,2.25,2.05,1.87,1.59,1.51,1.46,1.44,1.41])
                c = np.array([1.19,1.27,1.34,1.45,1.58,1.80,1.97,2.24,2.44])

            self.params = {"A":A,"b":b,"a":a,"c":c,"Delta":Delta}

    def get_param(self,param,Delta):

        if self.hmf_type == "Tinker08":

            ret = np.interp(Delta,self.params["Delta"],self.params[param])

        return ret

class constants:

    def __init__(self):

        self.c_light = 2.997924581e8
        self.G = 6.674*1e-11
        self.solar = 1.98855*1e30
        self.mpc = 3.08567758149137*1e22
        self.gamma =  self.G/self.c_light**2*self.solar/self.mpc
