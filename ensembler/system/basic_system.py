"""
Module: System
    This module shall be used to implement subclasses of system. It wraps all information needed and generated by a simulation.
"""
import os
import warnings

import numpy as np
import pandas as pd
import scipy.constants as const
from tqdm import tqdm

pd.options.mode.use_inf_as_na = True

# Typing
from ensembler.util.basic_class import _baseClass
from ensembler.util.ensemblerTypes import samplerCls, conditionCls, potentialCls, Number, Union, Iterable, NoReturn, \
    List

from ensembler.util import dataStructure as data

from ensembler.samplers.newtonian import newtonianSampler
from ensembler.samplers.stochastic import langevinIntegrator, metropolisMonteCarloIntegrator

from ensembler.potentials.OneD import metadynamicsPotential as metadynamicsPotential1D, harmonicOscillatorPotential
from ensembler.potentials.TwoD import metadynamicsPotential as metadynamicsPotential2D


class system(_baseClass):
    """
    The system class is managing the simulation approaches and all system data as well as the simulation results.

    """
    # static attributes
    name = "system"
    state = data.basicState
    verbose: bool

    # general attributes
    nParticles: int
    nDimensions: int
    nStates: int

    """
        Attributes
    """

    @property
    def potential(self) -> potentialCls:
        """
        The potential energy function class can be explored in a simulation

        Returns
        -------
        _potentialCls
            systems potential energy class
        """
        return self._potential

    @potential.setter
    def potential(self, potential: potentialCls):
        # if(issubclass(potential.__class__, _potentialCls)):
        self._potential = potential
        # else:
        #     raise ValueError("Potential needs to be a subclass of potential")

    @property
    def sampler(self) -> samplerCls:
        """
        The sampler method is used by the system to explore the potential energy function.

        Returns
        -------
        _samplerCls
            the sampler method that can be used to explore the potential energy function.

        """
        return self._integrator

    @sampler.setter
    def sampler(self, integrator: samplerCls):
        self._integrator = integrator

    @property
    def conditions(self) -> List[conditionCls]:
        """
        conditions list contains the system conditions.
        These conditions are applied during the sampling of the potential energy function to add additional constraints.

        Returns
        -------
        List[_conditionCls]
            the list of conditions coupled to the system.
        """
        return self._conditions

    @conditions.setter
    def conditions(self, conditions: List[conditionCls]):
        if (isinstance(conditions, List)):
            self._conditions = conditions
        else:
            raise ValueError("Conditions needs to be a List of objs, that are a subclass of _conditionCls")

    @property
    def total_system_energy(self) -> Number:
        """
        the total energy of the current system

        Returns
        -------
        Number
            total energy of the current system
        """
        return self._currentTotE

    @property
    def total_potential_energy(self) -> Number:
        """
            the total potential energy of the current system

        Returns
        -------
        Number
            total potential energy of the current system
        """
        return self._currentTotPot

    @property
    def total_kinetic_energy(self) -> Number:
        """
        the total kinetic energy of the current system

        Returns
        -------
        Number
            total kinetic energy of the current system
        """
        return self._currentTotKin

    @property
    def current_state(self) -> state:
        return self._currentState

    def set_current_state(self, current_position: Union[Number, Iterable[Number]],
                          current_velocities: Union[Number, Iterable[Number]] = 0,
                          current_force: Union[Number, Iterable[Number]] = 0,
                          current_temperature: Number = 298):
        """
        set_current_state
            set the current State of the system.

        Parameters
        ----------
        current_position: Union[Number, Iterable[Number]]
            new current system position
        current_velocities: Union[Number, Iterable[Number]], optional
            new current system velocity. (default: 0)
        current_force: Union[Number, Iterable[Number]], optional
            new current system force. (default: 0)
        current_temperature: Union[Number, Iterable[Number]], optional
            new current system temperature. (default: 298)

        """
        self._currentPosition = current_position
        self._currentForce = current_force
        self._currentVelocities = current_velocities
        self._currentTemperature = current_temperature
        self.currentState = self.state(self._currentPosition, self._currentTemperature, np.nan, np.nan, np.nan, np.nan,
                                       np.nan)

        self._update_energies()
        self.update_current_state()

    @property
    def trajectory(self) -> pd.DataFrame:
        return pd.DataFrame(list(map(lambda x: x._asdict(), self._trajectory)), columns=list(self.state.__dict__["_fields"]))

    @property
    def position(self) -> Union[Number, Iterable[Number]]:
        return self._currentPosition

    @position.setter
    def position(self, position: Union[Number, Iterable[Number]]):
        self._currentPosition = position
        if (len(self.trajectory) == 0):
            self.initial_position = self._currentPosition
        self._update_energies()
        self.update_current_state()

    def set_position(self, position: Union[Number, Iterable[Number]]):
        self.position = position

    @property
    def velocity(self) -> Union[Number, Iterable[Number]]:
        """
            velocity
                The current velocity of the system

        Returns
        -------
        Union[Number, Iterable[Number]]
        """
        return self._currentVelocities

    @velocity.setter
    def velocity(self, velocity: Union[Number, Iterable[Number]]):
        self._currentVelocities = velocity
        self._update_energies()
        self.update_current_state()

    def set_velocities(self, velocities):
        self.velocities = velocities

    @property
    def temperature(self) -> Number:
        """
        The set temperature of the system

        Returns
        -------
        Number
            set temperature
        """
        return self._temperature

    @temperature.setter
    def temperature(self, temperature: Number):
        self._temperature = temperature
        self._currentTemperature = temperature
        self._update_energies()

    def set_temperature(self, temperature: Number):
        """
            set Temperature
                set  the systems current temperature.

        Parameters
        ----------
        temperature

        """
        self.temperature = temperature

    @property
    def mass(self):
        return self._mass

    @mass.setter
    def mass(self, mass: float):
        self._mass = mass




    def __init__(self, potential: potentialCls=harmonicOscillatorPotential(), sampler: samplerCls=metropolisMonteCarloIntegrator(), conditions: Iterable[conditionCls] = None,
                 temperature: Number = 298.0, start_position: (Iterable[Number] or Number) = None, mass: Number = 1,
                 verbose: bool = True) -> NoReturn:
        """
            The system class is wrapping all components needed for a simulation.
            It can be used as the control unit for executing a simulation (simulate) and also to manage the generated data or input data.

        Parameters
        ----------
        potential : _potentialCls
            gives the potential function to be explored/sampled
        sampler : _samplerCls
            gives the method of choice to sample/explore the potential function
        conditions : Iterable[_conditionCls], optional
            apply the given conditions to the systems in a preset (tau) step iteration
        temperature : float, optional
            temperature of the system
        start_position : float, optional
            starting position of the system during the simulation
        mass : float, optional
            mass of the single particle
        verbose : bool, optional
            I can tell you a long iterative story...
        """

        ################################
        # Declare Attributes
        #################################

        ##Physical parameters
        self.nParticles = 1  # FUTURE: adapt it to be multiple particles
        self._mass = mass  # for one particle systems!!!!
        self._temperature = temperature

        # Output
        self._currentState = self.state(**{key: np.nan for key in self.state.__dict__["_fields"]})
        self._trajectory =[]

        # tmpvars - private:
        self._currentTotE: (Number) = np.nan
        self._currentTotPot: (Number) = np.nan
        self._currentTotKin: (Number) = np.nan
        self._currentPosition: (Number or Iterable[Number]) = np.nan
        self._currentVelocities: (Number or Iterable[Number]) = np.nan
        self._currentForce: (Number or Iterable[Number]) = np.nan
        self._currentTemperature: (Number or Iterable[Number]) = np.nan

        # BUILD System
        ## Fundamental Parts:
        self._potential = potential
        self._integrator = sampler

        if(conditions is None):
            self._conditions = []
        else:
            self._conditions = conditions

        ## set dim
        if (potential.constants[potential.nDimensions] > 0):
            self.nDimensions = potential.constants[potential.nDimensions]
        else:
            raise IOError(
                "Could not estimate the disered Dimensionality as potential dim was <1 and no initial position was given.")

        ###is the potential a state dependent one? - needed for initial pos.
        if (hasattr(potential, "nStates")):
            self.nStates = potential.constants[potential.nStates]
        else:
            self.nstates = 1

        # PREPARE THE SYSTEM
        # Only init velocities, if the samplers uses them
        if (issubclass(sampler.__class__, (newtonianSampler, langevinIntegrator))):
            init_velocity = True
        else:
            init_velocity = False

        self.initialise(withdraw_Traj=True, init_position=True, init_velocity=init_velocity,
                        set_initial_position=start_position)

        ##check if system should be coupled to conditions:
        # update for metadynamics simulation - local elevation bias is like a condition/potential hybrid.
        if (isinstance(self.potential, metadynamicsPotential1D) or isinstance(self.potential, metadynamicsPotential2D)):
            self._conditions.append(self.potential)

        for condition in self._conditions:
            if (not hasattr(condition, "system")):
                condition.couple_system(self)
            else:
                # warnings.warn("Decoupling system and coupling it again!")
                condition.couple_system(self)

            if (not hasattr(condition, "dt") and hasattr(self.sampler, "dt")):
                condition.dt = self.sampler.dt
            else:
                condition.dt = 1
        self.verbose = verbose


    """
        Initialisation
    """

    def initialise(self, withdraw_Traj: bool = True, init_position: bool = True, init_velocity: bool = True,
                   set_initial_position: Union[Number, Iterable[Number]] = None) -> NoReturn:
        """
            initialise
                initialises the system, i.e. can set an initial position, initial velocities and initialize the forces.

        Parameters
        ----------
        withdraw_Traj: bool, optional
            reset the simulation trajectory?
        init_position: bool, optional
            reinitialize the start_position - currentPosition
        init_velocity: bool, optional
            reinitialize the start_velocity - currentVelocity
        set_initial_position: Union[Number, Iterable[Number]], optional
            set the start_position to the given one.

        Returns
        -------
        NoReturn

        """
        if (withdraw_Traj):
            self.clear_trajectory()

        if (init_position):
            self._init_position(initial_position=set_initial_position)

        # Try to init the force
        try:
            self._currentForce = self.potential.force(self.initial_position)  # initialise forces!
        except:
            warnings.warn("Could not initialize the force of the potential? Check if you need it!")

        if (init_velocity):
            self._init_velocities()

        # set initial Temperature
        self._currentTemperature = self.temperature

        # update current state
        self.step = 0
        self.update_system_properties()
        self.update_current_state()

        self._trajectory.append(self.current_state)

    def _init_position(self, initial_position: Union[Number, Iterable[Number]] = None) -> NoReturn:
        """
            _init_position
                this function initializes the current position of the system.

        Parameters
        ----------
        initial_position: Union[Number, Iterable[Number]], optional
            if None, a random position is selected else the given position is used.

        """
        if (isinstance(initial_position, type(None))):
            self.initial_position = self.random_position()
        elif ((isinstance(initial_position, Number) and self.nDimensions == 1) or
              (isinstance(initial_position, Iterable) and all(
                  [isinstance(x, Number) for x in initial_position]) and self.nDimensions == len(initial_position))):
            self.initial_position = initial_position
        else:
            raise Exception("Did not understand the initial position! \n given: " + str(
                initial_position) + "\n Expected dimensions: " + str(self.nDimensions))
        self._currentPosition = self.initial_position

        self.update_current_state()
        return self.initial_position

    def _init_velocities(self) -> NoReturn:
        """
            _init_velocities
                Initializes the initial velocity randomly.

        """
        if (self.nStates > 1):
            self._currentVelocities = [[self._gen_rand_vel() for dim in range(self.nDimensions)] for s in
                                       range(self.nStates)] if (self.nDimensions > 1) else [self._gen_rand_vel() for
                                                                                            state in
                                                                                            range(self.nStates)]
        else:
            self._currentVelocities = [self._gen_rand_vel() for dim in range(self.nDimensions)] if (
                    self.nDimensions > 1) else self._gen_rand_vel()

        self.veltemp = self.mass / const.gas_constant / 1000.0 * np.linalg.norm(self._currentVelocities) ** 2  # t

        self.update_current_state()
        return self._currentVelocities

    def _gen_rand_vel(self) -> Number:
        """
            _gen_rand_vel
                get a random velocity according to the temperature and mass.

        Returns
        -------
        Number, Iterable[Number]
            a randomly selected velocity
        """
        return np.sqrt(const.gas_constant / 1000.0 * self.temperature / self.mass) * np.random.normal()

    def random_position(self) -> Union[Number, Iterable[Number]]:
        """
            randomPos
                returns a randomly selected position for the system.
        Returns
        -------
        Union[Number, Iterable[Number]]
            a random position
        """

        random_pos = np.squeeze(np.array(np.subtract(np.multiply(np.random.rand(self.nDimensions), 20), 10)))
        if (len(random_pos.shape) == 0):
            return np.float(random_pos)
        else:
            return random_pos

    """
        Update
    """

    def calculate_total_kinetic_energy(self) -> Union[Iterable[Number], Number]:
        """
            totKin
                returns the total kinetic energy of the system.
        Returns
        -------
        Union[Iterable[Number], Number, np.nan]
            total kinetic energy.
        """
        if (isinstance(self._currentVelocities, Number) or (isinstance(self._currentVelocities, Iterable) and all(
                [isinstance(x, Number) and not np.isnan(x) for x in self._currentVelocities]))):
            return np.sum(0.5 * self.mass * np.square(np.linalg.norm(self._currentVelocities)))
        else:
            return np.nan

    def calculate_total_potential_energy(self) -> Union[Iterable[Number], Number]:
        """
            totPot
                return the total potential energy

        Returns
        -------
        Union[Iterable[Number], Number]
            summed up total potential energies
        """
        return self.potential.ene(self._currentPosition)

    def update_system_properties(self) -> NoReturn:
        """
            updateSystemProperties
                updates the energies and temperature of the system

        Returns
        -------
        NoReturn

        """
        self._update_energies()
        self._update_temperature()

    def update_current_state(self) -> NoReturn:
        """
            updateCurrentState
                update current state from the _current vars.

        Returns
        -------
        NoReturn
        """
        self._currentState = self.state(self._currentPosition, self._currentTemperature,
                                        self._currentTotE, self._currentTotPot, self._currentTotKin,
                                        self._currentForce, self._currentVelocities)

    def _update_temperature(self) -> NoReturn:
        """

            this looks like a thermostat like thing! not implemented!@ TODO calc temperature from velocity

        Returns
        -------
        NoReturn

        """
        self._currentTemperature = self.temperature

    def _update_energies(self) -> NoReturn:
        """
            _updateEne
                update all total energy terms.

        Returns
        -------
        NoReturn

        """
        self._currentTotPot = self.calculate_total_potential_energy()
        self._currentTotKin = self.calculate_total_kinetic_energy()
        self._currentTotE = self._currentTotPot if (np.isnan(self._currentTotKin)) else np.add(self._currentTotKin,
                                                                                               self._currentTotPot)

    def _update_current_vars_from_current_state(self):
        """
            _update_current_vars_from_current_state
               update the _current Vars from the currentState

        Returns
        -------
        NoReturn

        """
        self._currentPosition = self.current_state.position
        self._currentTemperature = self.current_state.temperature
        self._currentTotE = self.current_state.total_system_energy
        self._currentTotPot = self.current_state.total_potential_energy
        self._currentTotKin = self.state.total_kinetic_energy
        self._currentForce = self.current_state.dhdpos
        self._currentVelocities = self.current_state.velocity

    def _update_state_from_traj(self) -> NoReturn:
        """
            _update_state_from_traj
                replaces the current state and the currentstate vars by the last trajectory state.

        Returns
        -------
        NoReturn

        """
        self.currentState = self.state(**self.trajectory.iloc[-1].to_dict())
        self._update_current_vars_from_current_state()
        return

    """
        Functionality
    """

    def simulate(self, steps: int,
                 withdraw_traj: bool = False, save_every_state: int = 1,
                 init_system: bool = False,
                 verbosity: bool = True, _progress_bar_prefix: str = "Simulation: ") -> state:
        """
            this function executes the simulation, by exploring the potential energy function with the sampling method for the given n steps.

        Parameters
        ----------
        steps: int
            number of integration steps
        init_system: bool, optional
            initialize the system. (default: False)
        withdraw_traj: bool, optional
            reset the current simulation trajectory. (default: False)
        save_every_state: int, optional
            save every n step. (and leave out the rest) (default: 1 - each step)
        verbosity: bool, optional
            change the verbosity of the simulation. (default: True)
        _progress_bar_prefix: str, optional
            prefix of tqdm progress bar. (default: "Simulation")

        Returns
        -------
        state
            returns the last current state
        """

        if (init_system):
            self._init_position()
            self._init_velocities()

        if (withdraw_traj):
            self._trajectory = []
            self._trajectory.append(self.current_state)

        self.update_current_state()
        self.update_system_properties()

        # progressBar or no ProgressBar
        if (verbosity):
            iteration_queue = tqdm(range(steps), desc=_progress_bar_prefix + " Simulation: ", mininterval=1.0,
                                   leave=verbosity)
        else:
            iteration_queue = range(steps)

        # Simulation loop
        for self.step in iteration_queue:

            # Do one simulation Step.
            self.propagate()

            # Apply Restraints, Constraints ...
            self.apply_conditions()

            # Calc new Energy&and other system properties
            self.update_system_properties()

            # Set new State
            self.update_current_state()

            if (self.step % save_every_state == 0 and self.step != steps - 1):
                self._trajectory.append(self.current_state)


        self._trajectory.append(self.current_state)
        return self.current_state

    def propagate(self) -> (
    Union[Iterable[Number], Number], Union[Iterable[Number], Number], Union[Iterable[Number], Number]):
        """
            propagate
                Do a single exploration step.
                Not stored in the trajectory and no energies returned or updated.

        Returns
        -------
        (Union[Iterable[Number], Number], Union[Iterable[Number], Number], Union[Iterable[Number], Number])
            returns the new current position, the new current velocities and the new current forces

        """
        self._currentPosition, self._currentVelocities, self._currentForce = self.sampler.step(self)
        return self._currentPosition, self._currentVelocities, self._currentForce

    def apply_conditions(self) -> NoReturn:
        """
            applyConditions
                this function applies the coupled conditions  to the current state of system.

        Returns
        -------
        NoReturn

        """

        for condition in self._conditions:
            condition.apply_coupled()

    def append_state(self, new_position: Union[Iterable[Number], Number], new_velocity: Union[Iterable[Number], Number],
                     new_forces: Union[Iterable[Number], Number]) -> NoReturn:
        """
            append_state
                appends a new state, based on the given arguments and updates the system to them.
        Parameters
        ----------
        new_position: Union[Iterable[Number], Number]
            a new position
        new_velocity: Union[Iterable[Number], Number]
            a new velocity
        new_forces: Union[Iterable[Number], Number]
            a new Force

        """
        self._currentPosition = new_position
        self._currentVelocities = new_velocity
        self._currentForce = new_forces

        self._update_temperature()
        self._update_energies()
        self.update_current_state()

        self._trajectory.append(self.current_state)

    def revert_step(self) -> NoReturn:
        """
            revertStep
                removes the last step which was performed from the trajectory and sets back the system to the one before.

        Returns
        -------
        NoReturn
        """
        if(len(self._trajectory)>1):
            self._trajectory.pop()
            self._currentState = self._trajectory[-1]
            self._update_current_vars_from_current_state()
        else:
            warnings.warn("Could not revert step, as only 1 step is in the trajectory!")
    def clear_trajectory(self):
        """
        deletes all entries of trajectory and adds current state as first timestep to the trajectory
        :return: None
        """
        self._trajectory = []

    def write_trajectory(self, out_path: str) -> str:
        """
            writeTrajectory
                Writes the trajectory out to a file.
        Parameters
        ----------
        out_path: str
            the string, where the traj csv should be stored.

        Returns
        -------
        str
            returns the out_path

        See Also
        ---------
        save

        """
        if (not os.path.exists(os.path.dirname(os.path.abspath(out_path)))):
            raise Exception("Could not find output folder: " + os.path.dirname(out_path))
        traj = self.trajectory
        traj.to_csv(out_path, header=True)
        return out_path
