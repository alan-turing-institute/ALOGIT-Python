"""
ALOGIT interface
"""

from .interface import Interface, requires_estimation
from .. import MultinomialLogit
import numpy as np
import os.path
import subprocess
import textwrap

_ALO_COMMAND_TITLE = '$title '
_ALO_COMMAND_ESTIMATE = '$estimate'
_ALO_COMMAND_COEFFICIENTS = '$coeff'
_ALO_COMMAND_ALTERNATIVES = "$nest root()"
_ALO_COMMAND_ARRAY = "$array"

_ALO_LABEL_CHOICE = 'ch'
_ALO_LABEL_CHOICE_COLUMN = 'alt'
_ALO_LABEL_AVAILABILITY = 'av'
_ALO_LABEL_VARIABLE = 'v'
_ALO_LABEL_CHOICE_DEPENDENT_VARIABLE = 'cv'
_ALO_LABEL_INTERCEPT = 'c'
_ALO_LABEL_PARAMETER = 'prm'

_MAX_CHARACTER_LENGTH = 10
_MAX_LINE_LENGTH = 77


class AlogitInterface(Interface):
    """
    ALOGIT interface class

    Args:
        model (ChoiceModel): The choice model to create an interface for.

    Keyword Args:
        alogit_path (str): Path to the ALOGIT executable.
        data_file (str, optional): Path of the file to hold model data in the
            format ALOGIT expects. If not supplied then a prefix is created
            based on the model title and appended with '.csv'
        alo_file (str, optional) Path of the ALOGIT input (.alo)
            file. If not supplied then a prefix is created based on the model
            title and appended with '.alo'
    """
    _valid_models = [MultinomialLogit]
    name = 'ALOGIT'

    def __init__(self, model, **kwargs):
        super().__init__(model)

        self.alogit_path = os.path.abspath(kwargs['alogit_path'])

        # Define a file prefix for the input and data files
        prefix = self.model.title.split(' ')[0]
        # Define file names
        if 'data_file' in kwargs:
            self.data_file = kwargs['data_file']
        else:
            self.data_file = prefix + '.csv'
        if 'alo_file' in kwargs:
            self.alo_file = kwargs['alo_file']
        else:
            self.alo_file = prefix + '.alo'

        # Create label abbreviations using ALOGIT's maximum character length
        self._create_abbreviations()

        # Create column labels
        column_labels = [self.abbreviate(label)
                         for label in model.data.columns]
        self.column_labels = column_labels

        # Create ALOGIT input file string
        self.alo = self._create_alo_file()

    def _create_abbreviations(self):
        """
        Create abbreviations of variable and parameter names conforming to
        ALOGIT's 10 character limit
        """
        model = self.model

        full = []
        abbreviations = []
        # Abbreviate choice names
        for number, choice in enumerate(model.alternatives, start=1):
            full.append(choice)
            abbreviations.append(_ALO_LABEL_CHOICE + str(number))

        # Abbreviate choice names / column label
        choice_column = model.choice_column
        full.append(choice_column)
        abbreviations.append(_ALO_LABEL_CHOICE_COLUMN)

        # Abbreviate availability column labels
        for number, availability in enumerate(model.availability.values(),
                                              start=1):
            full.append(availability)
            abbreviations.append(_ALO_LABEL_AVAILABILITY + str(number))

        # Abbreviate variable names and choice independent variable column
        # labels
        for number, variable in enumerate(model.all_variables(), start=1):
            full.append(variable)
            abbreviations.append(_ALO_LABEL_VARIABLE + str(number))

        # Abbreviate choice dependend variable column labels
        for number, variable in enumerate(
                model.alternative_dependent_variable_fields(),
                start=1
                ):
            full.append(variable)
            abbreviations.append(_ALO_LABEL_CHOICE_DEPENDENT_VARIABLE
                                 + str(number))

        # Abbreviate intercept names
        for number, intercept in enumerate(model.intercepts.values(), start=1):
            full.append(intercept)
            abbreviations.append(_ALO_LABEL_INTERCEPT + str(number))

        # Abbreviate parameter names
        for number, parameter in enumerate(model.parameters, start=1):
            full.append(parameter)
            abbreviations.append(_ALO_LABEL_PARAMETER + str(number))

        self.abbreviation = dict(zip(full, abbreviations))
        self.elongation = dict(zip(abbreviations, full))

    def abbreviate(self, string):
        """
        Abbreviate a string if its abbreviation has been defined.

        Args:
            string (str): The string to attempt to abbreviate.

        Returns:
            (str): The abbreviation of string if it has been defined by the
            interface, string otherwise.
        """
        if string in self.abbreviation:
            return self.abbreviation[string]
        else:
            return string

    def elongate(self, string):
        """
        Produce the long form of an abbreviation defined by the interface.

        Args:
            string (str): The string to elongate.

        Returns:
            (str): The long form of string as defined by the model.

        Raises:
            KeyError: If string is not an abbreviation defined by the
            interface.
        """
        return self.elongation[string]

    def _write_alo_file(self):
        """
        Write ALOGIT input file string to a file
        """
        # Use first word in title as file prefix
        with open(self.alo_file, 'w') as alo_file:
            for line in self.alo:
                alo_file.write(line + '\n')

    def _create_alo_file(self):
        """
        Create ALOGIT input file string
        """
        model = self.model
        alo = []
        # Write title
        alo += self._alo_record(_ALO_COMMAND_TITLE, model.title)
        # Estimate instruction
        alo += self._alo_record(_ALO_COMMAND_ESTIMATE)
        # Write coefficients (parameters and intercepts)
        alo += self._alo_record(
            _ALO_COMMAND_COEFFICIENTS,
            *model.parameters + list(model.intercepts.values())
            )
        # Write alternatives
        alo += self._alo_record(_ALO_COMMAND_ALTERNATIVES, *model.alternatives)
        # Write data file specification
        alo += self._specify_data_file()
        # Write availability columns
        for choice in model.alternatives:
            alo += self._alo_record(self._array_record('Avail', choice),
                                    model.availability[choice])
        # Define alternatives
        alo += self._define_alternatives()
        # Write choice dependent variable specification
        for variable, mapping in model.alternative_dependent_variables.items():
            # Define the choice dependent variable as an array with size
            # equal to the number of alternatives
            alo += self._alo_record(_ALO_COMMAND_ARRAY,
                                    self._array(variable, 'alts'))
            # Define the data file column corresponding to each choice
            for choice, column_label in mapping.items():
                alo += self._alo_record(
                    self._array_record(variable, choice), column_label)
        # Write utility specifications for each choice
        for choice in model.alternatives:
            alo += self._alo_record(self._array_record('Util', choice),
                                    self._utility_string(choice))
        return alo

    def _alo_record(self, command, *args):
        """
        Write a record to the ALOGIT input file
        """
        string = command
        for arg in args:
            string += ' ' + self.abbreviate(arg)
        return textwrap.wrap(string, width=_MAX_LINE_LENGTH,
                             break_long_words=False)

    def _array(self, array, argument):
        """
        Format an array in the form "array(argument)"
        """
        array = self.abbreviate(array)
        argument = self.abbreviate(argument)
        return array + '(' + argument + ')'

    def _array_record(self, array, argument):
        """
        Format an array record in the form "array(argument) ="
        """
        return self._array(array, argument) + ' ='

    def _specify_data_file(self):
        """
        Write the line specifying the data file and format to the ALOGIT
        input file.
        """
        # Create space seperated string of column labels
        column_labels = ' '.join(self.column_labels)
        string = 'file (name=' + self.data_file + ') ' + column_labels
        return textwrap.wrap(string, width=_MAX_LINE_LENGTH,
                             break_long_words=False)

    def _define_alternatives(self):
        """
        Create a record to explain the numeric encoding of alternatives
        """
        model = self.model
        string = 'choice=recode(' + _ALO_LABEL_CHOICE_COLUMN + ' ' + ', '.join(
            [self.abbreviate(choice) for choice in model.alternatives]) + ')'
        return textwrap.wrap(string, width=_MAX_LINE_LENGTH,
                             break_long_words=False)

    def _utility_string(self, choice):
        """
        Construct an ALOGIT style utility string
        """
        model = self.model
        utility = self.model.specification[choice]
        alternative_dependent_variables = (
            model.alternative_dependent_variables.keys()
            )

        # Intercept term
        if utility.intercept is not None:
            utility_string = [self.abbreviate(utility.intercept)]
        else:
            utility_string = []

        # parameter * variable terms
        for term in utility.terms:
            variable = term.variable
            # Format choice dependent variables
            if variable in alternative_dependent_variables:
                utility_string.append(
                    self.abbreviate(term.parameter) + '*'
                    + self.abbreviate(variable) + '('
                    + self.abbreviate(choice) + ')'
                    )
            else:
                utility_string.append(
                    self.abbreviate(term.parameter) + '*'
                    + self.abbreviate(term.variable)
                    )

        # Join all terms as a sum
        utility_string = ' + '.join(utility_string)
        return utility_string

    def _write_data_file(self):
        """
        Write the data in the format defined by the ALOGIT input file
        """
        model = self.model

        # Encode alternatives as numbers in new dataframe column
        number_of_alternatives = model.number_of_alternatives()
        choice_encoding = dict(
            zip(model.alternatives,
                np.arange(number_of_alternatives, dtype=float)+1)
            )
        model.data[_ALO_LABEL_CHOICE_COLUMN] = (
            model.data[model.choice_column].apply(lambda x: choice_encoding[x])
            )

        # Produce list of column labels replacing old choice column with the
        # new encoded choice column
        column_labels = list(model.data.columns)[:-1]
        column_labels[
            column_labels.index(model.choice_column)
            ] = _ALO_LABEL_CHOICE_COLUMN

        # Write data file
        with open(self.data_file, 'w') as data_file:
            model.data.to_csv(data_file, header=False, index=False,
                              line_terminator='\n',
                              columns=column_labels)

        # Drop encoded choice column
        model.data.drop(columns=_ALO_LABEL_CHOICE_COLUMN, inplace=True)

    def estimate(self):
        """
        Estimate the parameters of the choice model using ALOGIT.
        """
        # Write the input and data files
        self._write_alo_file()
        self._write_data_file()

        alo_path = os.path.abspath(self.alo_file)

        # Call ALOGIT
        process = subprocess.run([self.alogit_path, alo_path],
                                 capture_output=True)

        # Set estimated flag if ALOGIT ran successfully
        if process.returncode == 0:
            self._estimated = True
            self._parse_output_file()

        self.process = process

    def _parse_output_file(self, log_file_path=None):
        """
        Collect estimation data from the ALOGIT output file

        Args:
            log_file_path (str, optional): Path to the log file (used for
                testing).
        """
        if log_file_path:
            file_name = log_file_path
        else:
            # The filename and path is the same as the input but replacing the
            # extension .alo with .LOG
            file_name = os.path.splitext(
                os.path.abspath(self.alo_file)
                )[0] + '.LOG'

        # Get results from LOG file
        self._parameters = {}
        self._errors = {}
        self._t_values = {}
        with open(file_name, 'r') as outfile:
            for line in outfile:
                if 'Final value of Log Likelihood' in line:
                    self._final_log_likelihood = float(line.split()[-1])
                elif 'Initial Log Likelihood' in line:
                    self._null_log_likelihood = float(line.split()[-1])
                elif 'Coefficient   Estimate   Std. Error \'t\' ratio' in line:
                    for result in range(self.model.number_of_parameters(
                            include_intercepts=True)):
                        result_line = outfile.readline().split()
                        # Get model parameter name back from abbreviation
                        parameter = self.elongate(result_line[0])
                        self._parameters[parameter] = float(result_line[1])
                        self._errors[parameter] = float(result_line[2])
                        self._t_values[parameter] = float(result_line[3])
                elif 'Estimation time' in line:
                    self._estimation_time = float(line.split()[-2])

    @requires_estimation
    def display_results(self):
        process = self.process
        if process.returncode != 0:
            print('ALOGIT returned non-zero return code')
            print(process.stderr.decode('utf-8'))
        else:
            print(process.stdout.decode('utf-8'))

    @requires_estimation
    def null_log_likelihood(self):
        return self._null_log_likelihood

    @requires_estimation
    def final_log_likelihood(self):
        return self._final_log_likelihood

    @requires_estimation
    def parameters(self):
        return self._parameters

    @requires_estimation
    def standard_errors(self):
        return self._errors

    @requires_estimation
    def t_values(self):
        return self._t_values

    @requires_estimation
    def estimation_time(self):
        return self._estimation_time
