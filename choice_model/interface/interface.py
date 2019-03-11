"""
Base interface class definition
"""

from .. import ChoiceModel


class Interface(object):
    _valid_models = [ChoiceModel]

    def __init__(self, model):
        self._ensure_valid_model(model)
        self.model = model

    @classmethod
    def _ensure_valid_model(cls, model):
        if type(model) not in cls._valid_models:
            raise TypeError(
                'Argument "model" for cls.__name__ must be one of {}'.format(
                    [model_class.__name__ for model_class in cls._valid_models]
                    )
                )

    def estimate(self):
        """
        Estimate the parameters of the choice model.
        """
        raise NotImplementedError(
            'estimate has not been implemented in this class')
