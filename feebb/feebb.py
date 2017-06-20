# -*- coding: utf-8 -*-
"""
feebb - Finite Element Euler-Bernoulli Beams
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Feebb is a library for analysing beams using Euler-Bernoulli beam theory. It includes
a preprocessor to aid in building the model as well as a postprocessor for obtaining
forces and displacemnts at no-nodal locations.
"""
import json
import numpy as np


class Preprocessor:
    """Class for reading in preformatted input data for building the FEA model.

    Attributes:
        number_elements (int): Total number of elemnts in the model.
        elements (:obj:`list` of :obj:`dict`): A list of dictionaries. Each dictionary
            contains the defnition of a single beam element.
        supports (:obj:`list' of :obj:`int`): A list of the degrees of freedom at each
            node.

   """

    def __init__(self):
        """The Preprocessor class is initialized with all attributes as `None`."""

        self.reset()

    def __str__(self):
        return json.dumps(self.__dict__, indent=2, separators=(',', ': '))

    def reset(self):
        """Sets all attributes to `None`."""

        self.number_elements = None
        # self.loads = []
        self.elements = None
        self.supports = None

    def load_json(self, infile):
        """Reads on formatted input data from a .json file

        Args:
            infile (str): Name of the .json file to parse.

        """

        self.reset()
        with open(infile) as json_model:
            model = json.load(json_model)

        self.number_elements = len(model['elements'])
        # self.loads = [element['loads'] for element in model['elements']]
        self.elements = model['elements']
        self.supports = model['supports']


class Element:
    """Euler-Bernoulli beam element.

    This class is used to define a single finite element using Euler-Bernoulli beam
    theory. This is a 2-node element with 2 degrees of freedom per node.

    Attributes:
        stiffness (:obj:`numpy.array'): Local element stiffness matrix.
        nodal_loads (:obj:`numpy.array`): Nodal load vector.
        length (float): Length of element.
        E (float): Modulus of elasticity or Young's modulus of element.
        I (float): Moment of inertia of element.
        loads (:obj:`l

    """

    def __init__(self, preprocessed=None):
        self.stiffness = np.array([])
        self.nodal_loads = np.zeros((4))
        if preprocessed is None:
            self.length = 0
            self.E = 0
            self.I = 0
            self.loads = []
        else:
            self.length = preprocessed['length']
            self.E = preprocessed['youngs_mod']
            self.I = preprocessed['moment_of_inertia']
            self.loads = preprocessed['loads']
            self.local_stiffness()
            self.load_vector()

    def local_stiffness(self):
        """Local stiffness matrix for element."""

        kfv = 12 * self.E * self.I / self.length ** 3
        kmv = 6 * self.E * self.I / self.length ** 2
        kft = kmv
        kmt = 4 * self.E * self.I / self.length
        kmth = 2 * self.E * self.I / self.length
        self.stiffness = np.array([[kfv, -kft, -kfv, -kft],
                                   [-kmv, kmt, kmv, kmth],
                                   [-kfv, kft, kfv, kft],
                                   [-kft, kmth, kft, kmt]])

    def fer_point(self, p, a):
        """Fixed-end reactons due to point load."""

        b = self.length - a
        v = [(p * b ** 2 * (3*a + b)) / self.length ** 3, (p * a ** 2 * (a + 3 * b))
             / self.length ** 3]
        m = [p * a * b ** 2 / self.length ** 2, p * a ** 2 * b / self.length ** 2]
        load_vector = np.array([v[0], -m[0], v[1], m[1]])
        return load_vector

    def fer_distrib(self, w):
        """Fixed-end reactions due to uniformly distributed load."""

        v = w * self.length / 2
        m = w * self.length ** 2 / 12
        load_vector = np.array([v, -m, v, m])
        return load_vector

    def fer_patch(self, w, start, end):
        """Fixed-end reactions due to uniform "patch" load."""

        d = end - start
        a = start + d / 2
        b = self.length - a
        v = [(w * d) / self.length ** 3 * ((2 * a + self.length) * b ** 2
                                           + (a - b) / 4 * d ** 2),
             (w * d) / self.length ** 3 * ((2 * b + self.length) * a ** 2
                                           + (a - b) / 4 * d ** 2)]
        m = [(w * d / self.length ** 2) * (a * b ** 2 + (a - 2 * b) * d ** 2 / 12),
             (w * d / self.length ** 2) * (a ** 2 * b + (b - 2 * a) * d ** 2 / 12)]
        load_vector = np.array([v[0], -m[0], v[1], m[1]])
        return load_vector

    def fer_moment(self, m, a):
        """Fixed-end reactions due to concentrated moment."""

        pass

    def load_vector(self):
        """Resultant nodal load vector due to all loads on element."""

        for load in self.loads:
            if load['type'] == 'udl':
                self.nodal_loads = (self.nodal_loads
                                    + self.fer_distrib(load['magnitude']))
            elif load['type'] == 'point':
                self.nodal_loads = (self.nodal_loads
                                    + self.fer_point(load['magnitude'],
                                                     load['location']))
            elif load['type'] == 'patch':
                self.nodal_loads = (self.nodal_loads
                                    + self.fer_patch(load['magnitude'],
                                                     load['start'], load['end']))
            elif load['type'] == 'moment':
                self.nodal_loads = (self.nodal_loads
                                    + self.fer_moment(load['magnitude'],
                                                      load['location']))


class Beam():
    """Class for an assembly of elements into a single beam."""

    def __init__(self, elements, supports):
        self.len_elements = [element.length for element in elements]
        self.num_elements = len(elements)
        self.num_nodes = self.num_elements + 1
        self.num_dof = self.num_nodes * 2
        self.supports = supports
        self.stiffness = np.zeros((self.num_dof, self.num_dof))
        self.load = np.zeros((self.num_dof))
        for i, element in enumerate(elements):
            a = i * 2
            b = a + 4
            stiffness_element = np.zeros_like(self.stiffness)
            stiffness_element[a:b, a:b] = element.stiffness
            self.stiffness = self.stiffness + stiffness_element
            load_element = np.zeros_like(self.load)
            load_element[a:b] = element.nodal_loads
            self.load = self.load - load_element

        for i in range(self.num_dof):
            if self.supports[i] < 0:
                self.stiffness[i, :] = 0
                self.stiffness[:, i] = 0
                self.stiffness[i, i] = 1
                self.load[i] = 0

        self.displacement = np.linalg.solve(self.stiffness, self.load)


class Postprocessor():
    """Class of Hermite cubic interpolation functions and their derivatives."""

    def __init__(self, beam, num_points):
        self.beam = beam
        self.num_points = num_points

    def __phi_displacment(self, x, a):
        phi_1 = 1 - 3 * a ** 2 + 2 * a ** 3
        phi_2 = -x * (1 - a) ** 2
        phi_3 = 3 * a ** 2 - 2 * a ** 3
        phi_4 = -x * (a ** 2 - a)

        return np.array([phi_1, phi_2, phi_3, phi_4])

    def __phi_slope(self, length, a):
        phi_1 = -6 / length * a * (1 - a)
        phi_2 = -(1 + 3 * a ** 2 - 4 * a)
        phi_3 = -phi_1
        phi_4 = -a * (3 * a - 2)

        return np.array([phi_1, phi_2, phi_3, phi_4])

    def __phi_moment(self, length, a):
        phi_1 = -6 / length**2 * (1 - 2 * a)
        phi_2 = -2 / length**2 * (3 * a - 2)
        phi_3 = -phi_1
        phi_4 = -2 / length * (3 * a - 1)

        return np.array([phi_1, phi_2, phi_3, phi_4])

    def __phi_shear(self, length, a):
        phi_1 = 12 / length**3
        phi_2 = -6 / length**2
        phi_3 = -phi_1
        phi_4 = phi_2

        return np.array([phi_1, phi_2, phi_3, phi_4])

    def interp(self, action):
        # all functions dont have the same arguments FIX. probablly just use and if
        # in the for loop below
        interp_func = {'displacement': self.__phi_displacement,
                       'slope': self.__phi_slope,
                       'moment': self.__phi_moment,
                       'shear': self.__phi_shear}
        points = []
        for i in range(self.beam.num_elements):
            i_node = i * 2
            j_node = i_node + 4
            disp_nodes = self.beam.displacement[i_node:j_node]
            x_bar = np.linspace(0, self.beam.len_elements[i], self.num_points)
            a = x_bar / self.beam.len_elements[i]
            phi = interp_func[action](self.beam.len_elements[i], a)
            points.extend(np.sum(disp_nodes.reshape(4, 1) * phi, axis=0))

        return points
