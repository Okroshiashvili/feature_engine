from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.utils.validation import check_is_fitted

from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import roc_auc_score, mean_squared_error, r2_score

from feature_engine.dataframe_checks import _is_dataframe, \
    _check_input_matches_training_df

from feature_engine.variable_manipulation import _define_variables, \
    _find_all_variables


class ShuffleFeatures(BaseEstimator, TransformerMixin):

    """
    
    ShuffleFeatures reorganizes the values inside each feature, one feature 
    at the time, from a dataframe and determines how that permutation affects
    the performance metric of the machine learning algorithm.
    
    If the variables are important, a random permutation of their values will 
    decrease dramatically any of these metrics. Contrarily, the permutation of 
    values should have little to no effect on the model performance metric we 
    are assessing.
    

    Parameters
    ----------

    features_to_shuffle : str or list, default=None
        The list of variable(s) to be shuffled from the dataframe.
        If None, the transformer will shuffle all variables in the dataset.
        
    estimator: object, default = RandomForestClassifier()
        depending on 'regression' value
        Estimator can be a classifier or regressor
        
    scoring: str, default='neg_mean_squared_error'
        Desired metric to optimise the performance for the tree. Comes from
        sklearn metrics. See DecisionTreeRegressor or DecisionTreeClassifier
        model evaluation documentation for more options:
        https://scikit-learn.org/stable/modules/model_evaluation.html

    threshold: float
        the value that defines if a feature will be kept or removed.

    regression: boolean
        Indicates whether the discretiser should train a regression or a classification
        decision tree.

    cv : int, default=3
        Desired number of cross-validation fold to be used to fit the decision
        tree.
    
    """

    def __init__(self,
                 regression,
                 cv = 3,
                 threshold = 0,
                 features_to_shuffle = None,
                 estimator = None,
                 scoring = "neg_mean_squared_error"):
        
        
        if not isinstance(cv, bool):
            raise ValueError("cv can only take True or False")

        if not isinstance(regression, bool):
            raise ValueError("regression can only take True or False")
 
        self.features_to_shuffle = \
            _define_variables(features_to_shuffle)
    
        self.estimator = estimator
        
        self.scoring = scoring
        
        self.threshold = threshold
        
        self.regression = regression
        
        self.cv = cv

    def fit(self, X, y):
        """

        Parameters
        ----------
        
        X: pandas dataframe of shape = [n_samples, n_features]
            The input dataframe

        y: array-like of shape (n_samples) 
            Target variable. Required to train the estimator.


        Attributes
        ----------

        shuffled_features_: dict
            The shuffled features values

        """

        # check input dataframe

        X = _is_dataframe(X)
        
        # find all variables or check those entered are in the dataframe
        self.features_to_shuffle = _find_all_variables(X, self.features_to_shuffle)
        
        # Fit machine learning model with the input estimator if provided.
        # If the estimator is not provided, default to random tree model 
        # depending on value of self.regression
        
        if (self.estimator is not None):
            
            model = self.estimator.fit(X,
                                       y)
            y_pred = model.predict(X)
            model_performance = 1
            
        elif (self.regression):
            
            model = RandomForestRegressor().fit(X,
                                                y)
            y_pred = model.predict(X)
            model_performance = mean_squared_error(y, y_pred)
            
        else:
            
            model = RandomForestClassifier().fit(X,
                                                 y)
            y_pred = model.predict_proba(X)[:, 1]
            model_performance = roc_auc_score(y,
                                              y_pred)


        
        # dict to collect features and their performance_drift 
        
        self.features_performance_drifts_ = {}

        # shuffle features and save feature performance drift into a dict

        for feature in self.features_to_shuffle:

        #  Create a copy of X
            X_shuffled = X.copy()
                                       
            # shuffle individual feature
            X_shuffled[feature] = X_shuffled[feature].sample(frac=1).reset_index(drop=True)
            
            # Use fitted model to calculate new target prediction with
            # the shuffled feature.
            # Then, calculate this model performance.
            if (self.regression):
                
                shuffled_y_pred = model.predict(X_shuffled)
                shuffled_model_performance = mean_squared_error(y,
                                                                shuffled_y_pred)
                
            else:
                
                shuffled_y_pred = model.predict_proba(X_shuffled)[:, 1]
                shuffled_model_performance = roc_auc_score(y,
                                                           shuffled_y_pred)

             
            # Calculate drift in model performance after the feature has
            # been shuffled.
            drift = model_performance - shuffled_model_performance

            # Save feature and its performance drift in the 
            # features_performance_drifts_ attribute.
            self.features_performance_drifts_[feature] = drift

        return self

    def transform(self, X):
        """
        
        Updates the X dataframe with the new shuffled features.
    
        Parameters
        ----------
        
        X: pandas dataframe of shape = [n_samples, n_features].
            The input dataframe from which feature values will be shuffled.


        Returns
        -------

        X_transformed: pandas dataframe of shape = [n_samples, n_features - len(dropped features)] 
            Pandas dataframe with the selected features 
        """

        # check if fit is performed prior to transform

        check_is_fitted(self)

        # check if input is a dataframe

        X = _is_dataframe(X)

        # Create a list of the features to be kept depending on their 
        # performance drift and the threshold and the ML problem.
        
        if (self.regression):
            columns_to_drop = [feature for (feature, drift) in self.features_performance_drifts_.items() if drift >= self.threshold ]
        else:
            columns_to_drop = [feature for (feature, drift) in self.features_performance_drifts_.items() if drift <= self.threshold ]

        return X.drop(columns = columns_to_drop)
