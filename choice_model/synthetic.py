"""
Routines for creating synthetic models and corresponding data
"""

from .model import MultinomialLogit
import itertools
import numpy as np
import numpy.random as random
import pandas as pd
import scipy.stats as stats


def synthetic_model(title, number_of_alternatives, number_of_variables):
    """
    Create a synthetic model. In the model produced, the utility function for
    each alternative is simply a linear combination of all variables, there are
    no choice independent variables and all alternatives are available in each
    record.

    Args:
        title (str): Title for the model object.
        number_of_alternatives (int): Number of alternatives to generate.
        number_of_variables (int): Number of variables (and also parameters) to
            generate.

    Returns:
        (MultinomialLogit): Multinomial logit choice model object.
    """
    # Define alternatives in the format alternative1, alternative2, etc.
    alternatives = ['alternative{}'.format(number)
                    for number in range(1, number_of_alternatives+1)]
    # Define availability columns in the format availability1, availability2,
    # etc.
    availability = {alternative: 'availability{}'.format(number+1)
                    for number, alternative in enumerate(alternatives)}
    # Define choice dependent variable columns in the format
    # alternative1_variable1, alternative1_variable2, etc.
    variables = {}
    for number in range(1, number_of_variables+1):
        variables['variable{}'.format(number)] = {
            alternative: '{}_variable{}'.format(alternative, number)
            for alternative in alternatives
            }
    # Define intercept names in the format c1, c1, etc.
    intercepts = {alternative: 'c{}'.format(number+1)
                  for number, alternative in enumerate(alternatives[:-1])}
    # Define parameters in the format parameter1, parameter2, etc.
    parameters = ['parameter{}'.format(number)
                  for number in range(1, number_of_variables+1)]

    # Create linear combination terms i.e. parameter1*variable1 +
    # parameter2*variable2 + ...
    all_variables = variables.keys()
    products = ['*'.join(pair) for pair in zip(parameters, all_variables)]
    linear_combination = ' + '.join(products)
    # Construct utility function strings. The last alternative does not have an
    # intercept
    specification = {}
    for alternative in alternatives[:-1]:
        specification[alternative] = (
            ' + '.join([intercepts[alternative], linear_combination])
            )
    specification[alternatives[-1]] = linear_combination

    model = MultinomialLogit(
        title=title,
        alternatives=alternatives,
        choice_column='choice',
        availability=availability,
        alternative_independent_variables=[],
        alternative_dependent_variables=variables,
        intercepts=intercepts,
        parameters=parameters,
        specification=specification
        )
    return model


def synthetic_data(model, n_observations):
    """
    Generate synthetic data for a model.

    The variables for each observation are picked from a multivariate gaussian
    distribution with mean 5 and a covariance matrix of the form :math:`A^T A`
    where the elements of A are picked from the uniform distribution in the
    range [-1.0, 1.0).

    All parameters are set to -1.5 divided by the number of parameters, and
    intercepts to 0.

    The choice for each observation is the alternative with maximum utility
    plus an unkown factor taken from the Gumbel distribution.

    Args:
        model (ChoiceModel): The choice model object to create synthetic
            observations for.
        n_observations (int): The number of synthetic observations to create.

    Returns:
        (DataFrame): A pandas dataframe of synthetic data that can be
            loaded into model.
    """
    n_alternatives = model.number_of_alternatives()
    n_parameters = model.number_of_parameters(include_intercepts=False)
    n_variables = model.number_of_variables()

    # Set mean value for all alternative dependent variables
    mean = [5.]*n_variables

    # Generate a (symmetric) positive semi-definite covariance matrix
    covariance = random.uniform(
        -1.0, 1.0, [n_variables, n_variables]
        )
    covariance = np.matmul(covariance.T, covariance)

    # Pick variables for each observations from the multivariate gaussian
    # distribution defined by mean and covariance
    variables = stats.multivariate_normal.rvs(mean, covariance,
                                              [n_observations, n_alternatives])

    # Set parameters for each alternative
    parameters = np.full(fill_value=-1.5, shape=n_parameters)
    parameters = parameters / n_parameters
    utility = np.zeros([n_observations, n_alternatives])

    # Calculate the 'ideal' utility values for each obsertvation and
    # alternative, a linear combination of the relevant parameters and
    # variables
    for observation, alternative in itertools.product(range(n_observations),
                                                      range(n_alternatives)):
        utility[observation, alternative] = (
                np.dot(parameters, variables[observation, alternative, :])
                )

    # Add unknown factor, drawn from the Gumbel distribution, to each utility
    utility += random.gumbel(size=[n_observations, n_alternatives])

    # Find the choice for each observation, the alternative with the highest
    # utility
    choices = utility.argmax(axis=1)

    # Create dataframe with the necessary column labels
    data = pd.DataFrame(
        columns=(model.all_variable_fields() +
                 model.availability_fields() +
                 [model.choice_column])
        )

    # Enter choices
    data[model.choice_column] = [model.alternatives[choice]
                                 for choice in choices]
    # Set all availabilities to true
    for availability in model.availability_fields():
        data[availability] = np.full(shape=n_observations, fill_value=1)
    # Set value of each (alternative dependent) variable for all observations
    for i, variable in enumerate(model.alternative_dependent_variables):
        for j, alternative in enumerate(model.alternatives):
            data[
                model.alternative_dependent_variables[variable][alternative]
                ] = variables[:, j, i]

    return data


def synthetic_data_uniform(model, number_of_records):
    """
    Generate uniform, random synthetic data for a model.

    The data generated by this function has no correlation to the choices. This
    data is therefore not realistic.

    Args:
        model (ChoiceModel): The choice model object to create synthetic
            observations for.
        number_of_records (int): The number of synthetic observations to
            create.

    Returns:
        (DataFrame): A pandas dataframe of synthetic data that can be
            loaded into model.
    """
    # Create dataframe with the necessary column labels
    data = pd.DataFrame(
        columns=(model.all_variable_fields() +
                 model.availability_fields() +
                 [model.choice_column])
        )

    # Populate the choice column with alternatives picked uniformly from the
    # models alternatives
    alternatives = model.alternatives
    data[model.choice_column] = random.choice(alternatives,
                                              size=number_of_records)

    # Set all availability columns to 1 (available)
    for column in model.availability_fields():
        data[column] = np.full(shape=number_of_records, fill_value=1)

    # Fill all variable columns with uniform random numbers in the range
    # [0,1)
    for column in model.all_variable_fields():
        data[column] = random.random(size=number_of_records)

    return data
