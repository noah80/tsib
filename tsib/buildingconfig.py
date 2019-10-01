# -*- coding: utf-8 -*-
"""
Created on Wed Oct 11 21:17:37 2017

@author: Leander
"""

import os
import time
import copy
import pandas as pd
import numpy as np
import multiprocessing as mp
import tsib.timeseriesmanager as tsm
from tsib.electric.CREST import run_district_year, one_household_year

import warnings

HEAT_TECHS = [
    "Oil boiler",
    "Gas boiler",
    "Heat pump",
    "Pellet boiler",
    "Electric heater",
    "District heating",
]

DATA_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "data")

TOTAL_PROFILE_NUM = 20

KWARG_TYPES = {
    "n_storey": "NOT_IMPLEMENTED",  # number of storeys in the building
    "a_ref_app": float,  # living area of a single flat
    "a_ref": float,  # living area of the whole building
    "n_apartments": int,  # number of flats
    "surrounding": [
        "Detached",
        "Semi",
        "Terraced",
    ],  # if the house is standing alone or is surrounded
    "ID": str,  # direct identification of an IWU building by its ID
    "buildingYear": int,  # construction year
    "buildingType": [
        "AB",
        "SFH",
        "MFH",
        "TH",
    ],  # type of building (can be inherited by n_apartments)
    "buildingClassification": ["Gen", "HR", "Lightframe"],
    "eastOrOverall": ["N", "East"],
    "roofOrientation": float,  # roof azimuth with 180 as south
    "roofTilt": float,  # rooftile angle in degree
    "refurbished": bool,  # if the building is already refurbished
    "buildnew": bool,  # if the building gets completely new constructed
    "onlyEnergyInvest": bool,  # if the cost of refurbishing the walls and the roof are only energy related
    "thermalClass": "NOT_IMPLEMENTED",  # ['very light', 'light', 'medium', 'heavy', 'very heavy'],
    "refurbishment": bool,  # if refurbishment options (changing insulation or ventilation) shall be considered
    "force_refurbishment": bool,  # if refurbishment must be selected
    "hotWaterElec": bool,  # if hot water is electrically provided
    "existingHeatSupply": [
        "Oil boiler",
        "Gas boiler",
        "Heat pump",
        "Pellet boiler",
        "Electric heater",
        "CHP",
        "District heating",
    ],
    "replaceHeatSupply": bool,  # if heat supply is at the end if the life time
    "T_sup": float,  # design supply temperature of the building
    "floorHeating": bool,  # if a floor heating is available --> set the supply temperature
    "ownership": bool,  # if the occupant is also the owner
    "WACC": float,  # interest rate - otherwise inherited from ownership
    "weatherData": pd.DataFrame,  # time series with the weather
    "weatherID": str,  # identifier of the chosen weather data
    "getNetCDF4": bool,  # if chosen
    "year": int,  # year for which it shall get optimized
    "longitude": float,  # longitude in degree
    "latitude": float,  # latitude in degree
    "nightReduction": bool,  # night reduction of comfort temperature
    "occControl": bool,  # if the heating is adapted to occupancy activity
    "capControl": bool,  # if the heat storage capacity of the bdg can be used
    "comfortT_lb": float,  # lower bound of the comfortable temperature if active
    "comfortT_ub": float,  # upper bound of the comfortable temperature if active
    "n_persons": int,  # number of persons living in a single flat
    "elecLoad": pd.Series,  # electricity load profile of the flat with correct time index
    "elecLoadID": str,  # identifier of the load
    "hasFirePlace": bool,  # if the building has a fire place
    "hasSolarThermal": bool,  # if the building has solar thermal to provide hot water
    "hasPhotovoltaic": bool,  # if the building has a photovoltaic panel
    "varyoccupancy": int,  # for how many occupancy profiles the building shall be optimized
    "mean_load": bool,  # if the fluctuative profile or the mean hourly profile should be taken
    "windows_refurbished": "NOT_IMPLEMENTED",  # if the windows have allready been replaced
    "walls_refurbished": "NOT_IMPLEMENTED",  # if the walls have already gotton an additional insulation
    "roof_refurbished": "NOT_IMPLEMENTED",  # if the roof area has already gotton an additional insulation
    "costdata": str,  # file identifier with the related cost data
}

KWARG_DEFAULTS = {
    "roofOrientation": 135.0,  # roof azimuth with 180 as south
    "refurbished": False,  # if the building is already refurbished
    "buildnew": False,  # if the building is newly constructed
    "onlyEnergyInvest": False,  # if the cost of refurbishing the walls and the roof are only energy rlated
    "thermalClass": "medium",
    "refurbishment": True,  # if refurbishment options (changing insulation) shall be considered
    "force_refurbishment": False,  # if refurbishment must be selected
    "hotWaterElec": False,  # if hot water is electrically provided
    "existingHeatSupply": "Oil boiler",
    "buildingYear": 1990,  # construction year
    "replaceHeatSupply": True,  # if heat supply is at the end if the life time
    "hasPhotovoltaic": False,  # if it exists already a photovoltaic panel
    "floorHeating": False,  # if a floor heating is available --> set the supply temperature
    "ownership": True,  # if the occupant is also the owner
    "getNetCDF4": False,  # if chosen
    "year": 2010,  # year for which it shall get optimized
    "longitude": 8.0,  # longitude in degree
    "latitude": 50.0,  # latitude in degree
    "nightReduction": True,  # night reduction of comfort temperature
    "capControl": True,  # if the heating capacity of the building can be used
    "occControl": False,  # if the heating is adapted to occupancy activity
    "comfortT_lb": 21.0,  # lower bound of the comfortable temperature if active
    "comfortT_ub": 24.0,  # upper bound of the comfortable temperature if active
    "varyoccupancy": 1,  # for how many occupancy profiles the building shall be optimized
    "mean_load": False,  # if the fluctuative profile or the mean hourly profile should be taken
    "costdata": "default_2016",
}


class BuildingConfiguration(object):
    """
    Class which configures building types and decides based on the provision
    of parameters dynamically how to set the building ID and which parameters
    from which database have to get added.


    """

    def __init__(self, kwargs, database=None, ignore_profiles=False):
        """
        Initialize a unique building configuration which provides
        database identifier and configuration parameters based on the user
        input
        
        Parameters
        ----------
        ignore_profiles: bool, optional (default = False)
            If the profiles should or should not be loaded during
            initialization. Basically this is only required for database
            access.
        """
        if not isinstance(kwargs, dict):
            raise ValueError("kwargs needs to be dictionary with all the parameters")

        # validate if the input parameters are correct
        for kwarg in list(kwargs):
            if not isinstance(kwarg, str):
                raise ValueError("Keyword identifiers need to be strings")
            # drop not defined keywords from dictionary
            elif kwargs[kwarg] is None:
                kwargs.pop(kwarg)
            elif kwarg in KWARG_TYPES:
                # check if implemented
                if KWARG_TYPES[kwarg] is "NOT_IMPLEMENTED":
                    raise NotImplementedError(
                        kwarg + " is not yet considered as keyword"
                    )
                # check for keywords which can only be a limited set of values
                elif type(KWARG_TYPES[kwarg]) is list:
                    if not kwargs[kwarg] in KWARG_TYPES[kwarg]:
                        raise ValueError(
                            "'"
                            + kwarg
                            + "' needs to be one of "
                            + "the following: "
                            + "{}".format(KWARG_TYPES[kwarg])
                        )
                    else:
                        pass  # is valid
                # check the data type of the keyword argument
                elif KWARG_TYPES[kwarg] is float:
                    if not isinstance(
                        kwargs[kwarg], (np.float16, np.float32, np.float64, float)
                    ):
                        raise ValueError(
                            "'" + kwarg + "' needs to be of " + str(KWARG_TYPES[kwarg])
                        )
                    else:
                        pass  # is valid
                elif KWARG_TYPES[kwarg] is int:
                    if not isinstance(
                        kwargs[kwarg], (np.int8, np.int16, np.int32, np.int64, int)
                    ):
                        raise ValueError(
                            "'" + kwarg + "' needs to be of " + str(KWARG_TYPES[kwarg])
                        )
                    else:
                        pass  # is valid
                elif KWARG_TYPES[kwarg] is bool:
                    if not isinstance(kwargs[kwarg], (bool, np.bool, np.bool_)):
                        raise ValueError(
                            "'" + kwarg + "' needs to be of " + str(KWARG_TYPES[kwarg])
                        )
                    else:
                        pass  # is valid
                elif not isinstance(kwargs[kwarg], KWARG_TYPES[kwarg]):
                    raise ValueError(
                        "'" + kwarg + "' needs to be of " + str(KWARG_TYPES[kwarg])
                    )
                else:
                    pass  # is valid
            else:
                raise ValueError(kwarg + " is not a valid keyword argument")

        # fill some of the other kwargs with default values
        self.inputKwargs = copy.deepcopy(kwargs)
        for def_kwarg in KWARG_DEFAULTS:
            if not def_kwarg in self.inputKwargs:
                self.inputKwargs[def_kwarg] = KWARG_DEFAULTS[def_kwarg]

        self.IDentries = {}
        # init building configurator
        self.cfg = {}

        self.ignore_profiles = ignore_profiles

        if not database is None:
            raise NotImplementedError()
        return

        # TODO: get just ID

    def getBdgCfg(self, includeSupply=True):
        """
        Returns a dictionary which is used, either to parameterize
        the buildingmodel.Building or the buildingopt.BuildingOpt

        Parameters
        ----------
        includeSupply: bool, optional (default: True)
            Decides wether also parameters for the supply optimization
            should be included.
        """
        # TODO integrate a function which drops used keyword arguments

        if self.cfg:
            return self.cfg
        else:
            # get the iwu database
            self.iwu_bdg = pd.read_csv(
                os.path.join(DATA_PATH, "IWU", "IWU_wPersons.csv"), index_col=0
            )

            # call all functions which populate the building configurator
            cfg = self.cfg
            cfg = self._get_form(cfg, self.inputKwargs)
            cfg = self._get_fabric(cfg, self.inputKwargs)
            cfg = self._get_operation(cfg, self.inputKwargs)
            if includeSupply:
                cfg = self._get_equipment(cfg, self.inputKwargs)
            cfg = self._get_finance(cfg, self.inputKwargs)

            # check if cost data file exists
            if not os.path.exists(
                os.path.join(
                    DATA_PATH, "costdata", self.inputKwargs["costdata"] + ".xlsx"
                )
            ):
                raise ValueError(
                    "'costdata' file with name '"
                    + self.inputKwargs["costdata"]
                    + "' does not exists"
                )
            # add cost data
            cfg["costdata"] = self.inputKwargs["costdata"]

            self.IDentries["costdata"] = cfg["costdata"]
            return cfg

    def _get_operation(self, cfg, kwgs):
        """
        Gets all parameters which are relevant for the operation of the system.
        """
        cfg["latitude"] = kwgs["latitude"]
        cfg["longitude"] = kwgs["longitude"]

        if "weatherData" in kwgs:
            if not "weatherID" in kwgs:
                raise ValueError(
                    "If weatherData is defined, also " + "weatherID has to be defined"
                )
            else:
                cfg["weather"] = kwgs["weatherData"]
                cfg["design_T_min"] = cfg["weather"].min()["T"]
                cfg["weatherID"] = kwgs["weatherID"]
                if (
                    kwgs["longitude"] == KWARG_DEFAULTS["longitude"]
                    or kwgs["latitude"] == KWARG_DEFAULTS["latitude"]
                ):
                    warnings.warn(
                        "longitude and latitude are set to "
                        + "default values. It can cause an error in "
                        "the solar irration simulation"
                    )

        else:
            # get TRY weather and ISO
            cfg["weather"], cfg["design_T_min"], cfg[
                "weatherID"
            ] = get_ISO12831_weather(
                kwgs["longitude"],
                kwgs["latitude"],
                year=kwgs["year"],
                cosmo=kwgs["getNetCDF4"],
            )

        # save relevant ID entries
        self.IDentries["T_min"] = cfg["design_T_min"]
        self.IDentries["weather"] = cfg["weatherID"]

        # get controller booleans
        for control in ["nightReduction", "occControl", "capControl"]:
            cfg[control] = kwgs[control]
            self.IDentries[control] = cfg[control]

        # get comfort zone
        cfg["comfortT_lb"] = kwgs["comfortT_lb"]
        cfg["comfortT_ub"] = kwgs["comfortT_ub"]
        self.IDentries["ComfortZone"] = (
            str(cfg["comfortT_lb"]) + "-" + str(cfg["comfortT_ub"])
        )
        if cfg["comfortT_lb"] >= cfg["comfortT_ub"] - 0.5:
            warnings.warn(
                "If the gap is too small, the solver can run into"
                + " numerical troubles",
                UserWarning,
            )

        # get occupancy
        if "n_persons" in kwgs:
            cfg["n_persons"] = kwgs["n_persons"]
        else:
            cfg["n_persons"] = self.iwu_bdg.loc[self.IDentries["Shape"], "n_persons"]
            warnings.warn('number of persons. "n_persons" is inherited from IWU')

        if "n_apartments" in kwgs:
            cfg["n_apartments"] = kwgs["n_apartments"]
        else:
            cfg["n_apartments"] = self.iwu_bdg.loc[
                self.IDentries["Shape"], "n_Apartment"
            ]
            warnings.warn('number of app. "n_apartments" is inherited from IWU')
        self.IDentries["n_persons"] = cfg["n_persons"]
        self.IDentries["n_apartments"] = cfg["n_apartments"]

        if "elecLoad" in kwgs:
            if not "elecLoadID" in kwgs:
                raise ValueError(
                    "If elecLoad is defined, also " + " elecLoadID has to be defined"
                )
            else:
                cfg["elecLoad"] = kwgs["elecLoad"]
                self.IDentries["elecLoad"] = kwgs["elecLoadID"]
                addElecLoad = False
        else:
            self.IDentries["elecLoad"] = (
                "CREST_" + str(cfg["n_persons"]) + "x" + str(cfg["n_apartments"])
            )
            addElecLoad = True

        # define if an fire place is in the building
        if "hasFirePlace" in kwgs:
            cfg["hasFirePlace"] = kwgs["hasFirePlace"]
        else:
            # define oven only for building where the appartments are bigger
            # than 100 m^2 -> self chosen value
            if float(cfg["A_ref"]) / cfg["n_apartments"] >= 100.0:
                cfg["hasFirePlace"] = True

                # define size of the oven - atm just a fix value of 10 kW per flat
                cfg["fireplaceSize"] = 10.0 * cfg["n_apartments"]
            else:
                cfg["hasFirePlace"] = False
        self.IDentries["hasFirePlace"] = cfg["hasFirePlace"]

        # if a varying occupancy profile should get integrated
        if "varyoccupancy" in kwgs:
            cfg["varyoccupancy"] = kwgs["varyoccupancy"]
            if cfg["varyoccupancy"] < 1:
                raise ValueError('"varyoccupancy" needs to be at least 1.')
        else:
            cfg["varyoccupancy"] = 1
        self.IDentries["varyoccupancy"] = cfg["varyoccupancy"]

        # if the mean profile or the fluctuation pad profile should be taken
        cfg["mean_load"] = kwgs["mean_load"]
        self.IDentries["mean_load"] = cfg["mean_load"]

        # create seed for every building
        state_seed = (
            str(int(cfg["n_persons"]))
            + str(int(cfg["longitude"] * 100))[2:]
            + str(int(cfg["A_ref"]))
        )
        if len(state_seed) > 8:
            state_seed = state_seed[:8]
        state_seed = int(state_seed)

        # get the profiles
        if not self.ignore_profiles:
            cfg = self.get_building_profile(
                cfg, kwgs, state_seed, addElecLoad=addElecLoad
            )

        return cfg

    def get_building_profile(self, cfg, kwgs, state_seed, addElecLoad=True):
        """
        Get all the occupancy related data, like internal heat gain,
        electricity load and occupants activity.
        """

        # get a number of random seeds to generate the profiles
        seeds = np.random.RandomState(state_seed).randint(
            0, TOTAL_PROFILE_NUM, size=int(cfg["varyoccupancy"] * cfg["n_apartments"])
        )

        # get the profiles
        hh_profiles = get_household_profiles(
            cfg["n_persons"],
            cfg["weather"],
            self.IDentries["weather"],
            seeds=seeds,
            ignore_weather=True,
            mean_load=cfg["mean_load"],
        )

        # get short form apartments
        n_app = int(cfg["n_apartments"])
        # abs number of occupants
        n_occs = int(cfg["n_persons"]) * n_app

        # get from the household profiles buildingprofiles
        bdg_profiles = {}

        # get a profile for each occupancy variation
        for i in range(cfg["varyoccupancy"]):
            if n_app == 1:
                occData = hh_profiles[i]
            else:
                # merge profiles for multiple appartments
                occData = pd.concat(
                    hh_profiles[i * n_app : (i + 1) * n_app],
                    keys=range(i * n_app, (i + 1) * n_app),
                )
                occData = occData.groupby(level=[1]).sum()

            bdg_profiles[i] = {}

            # heat gain values relative (Master thesis cheng feng)
            OccNotActiveHeatGain = 100
            OccActiveHeatGain = 150

            # internal heat gain [kW]
            bdg_profiles[i]["Q_ig"] = (
                occData["AppHeatGain"].values
                + occData["OccActive"].values * OccActiveHeatGain
                + occData["OccNotActive"].values * OccNotActiveHeatGain
            ) / 1000
            #        bdg_profiles[i]['occ_active'] = occData['OccActive'] > 0.0

            # the share of occupants which is not at home
            bdg_profiles[i]["occ_nothome"] = (
                n_occs - occData["OccActive"] - occData["OccNotActive"]
            ) / n_occs

            # the share of occupants which is sleeping
            bdg_profiles[i]["occ_sleeping"] = occData["OccNotActive"].div(n_occs)
            if addElecLoad:
                bdg_profiles[i]["elecLoad"] = occData["Load"] / 1000

            # get hot water load
            bdg_profiles[i]["hotWaterLoad"] = occData["HotWater"] / 1000

            # overall number of occupants
            bdg_profiles[i]["n_occupants"] = n_occs

            # get fireplace profile
            if cfg["hasFirePlace"]:
                pot_filename = os.path.join(
                    DATA_PATH,
                    "results",
                    "fireplaceprofiles",
                    "Profile"
                    + "_apps"
                    + str(int(n_app))
                    + "_occ"
                    + str(int(cfg["n_persons"]))
                    + "_wea"
                    + str(cfg["weatherID"])
                    + "_seed"
                    + str(state_seed)
                    + ".csv",
                )
                if os.path.isfile(pot_filename):
                    fireplaceLoad = pd.read_csv(
                        pot_filename,
                        index_col=0,
                        header=None,
                        parse_dates=True,
                        squeeze=True,
                    )
                else:
                    # get oven profile depending on activity and outside temperature
                    fireplaceLoad = tsm.createWoodFireProfile(
                        cfg["weather"]["T"],
                        occData["OccActive"] / n_occs,
                        n_ovens=n_app,
                        T_oven_on=5,
                        t_cool=5.0,
                        fullloadSteps=450,
                        seed=state_seed,
                    )
                    fireplaceLoad.to_csv(pot_filename)

                bdg_profiles[i]["fireplaceLoad"] = fireplaceLoad

        # give building config the first profile
        cfg.update(bdg_profiles[i])

        # give the other profiles to the configuration file as well
        if cfg["varyoccupancy"] > 1:
            cfg["vary_profiles"] = bdg_profiles

        return cfg

    def _get_form(self, cfg, kwgs):

        ### Get the correct shape of building
        if (
            "a_ref_app" in kwgs and "n_apartments" in kwgs and "surrounding" in kwgs
        ) or ("a_ref" in kwgs and "surrounding" in kwgs):
            # calculate full reference area
            if "a_ref" in kwgs and "surrounding" in kwgs:
                a_ref = kwgs["a_ref"]
            else:
                a_ref = kwgs["a_ref_app"] * kwgs["n_apartments"]

            # save the number of apps
            cfg["n_apartments"] = kwgs["n_apartments"]

            # reduce to buildings with equivalent surrounding
            surDict = {"B_Alone": "Detached", "B_N1": "Semi", "B_N2": "Terraced"}
            self.iwu_bdg.replace({"Code_AttachedNeighbours": surDict}, inplace=True)
            iwu_sur = self.iwu_bdg[
                self.iwu_bdg["Code_AttachedNeighbours"] == kwgs["surrounding"]
            ]

            # TODO: validate that this works

            # get the most similar building

            diff_area = abs(iwu_sur["A_C_Ref"] - a_ref)

            iwu_idx = diff_area.idxmin()

            iwu_bdg = self.iwu_bdg.xs(iwu_idx).to_dict()

        elif "ID" in kwgs:
            iwu_bdg = self.iwu_bdg.ix[kwgs["ID"]].to_dict()
            a_ref = iwu_bdg["A_C_Ref"]
            cfg["n_apartments"] = iwu_bdg["n_Apartment"]
            iwu_idx = kwgs["ID"]
        elif "buildingYear" and "buildingType" in kwgs:

            if "buildingClassification" in kwgs:
                bdg_class = kwgs["buildingClassification"]
            else:
                bdg_class = "Gen"
            if "eastOrOverall" in kwgs:
                bdg_eastwest = kwgs["eastOrOverall"]
            else:
                bdg_eastwest = "N"

            iwu_bdg = self.iwu_bdg[
                (self.iwu_bdg["Year1_Building"] <= kwgs["buildingYear"])
                & (kwgs["buildingYear"] <= self.iwu_bdg["Year2_Building"])
                & (self.iwu_bdg["Code_BuildingSizeClass"] == kwgs["buildingType"])
            ]
            # ugly but pycharm complains otherwise
            is_class = [
                bdg_class in btype.split(".") for btype in iwu_bdg["Code_BuildingType"]
            ]
            iwu_bdg = iwu_bdg[is_class]
            is_eastwest = [
                bdg_eastwest in btype.split(".")
                for btype in iwu_bdg["Code_BuildingType"]
            ]
            iwu_bdg = iwu_bdg[is_eastwest]
            # test if a building was chosen
            if not iwu_bdg.index.any():
                raise ValueError(
                    "Building with this definition does not exist in IWU-Database"
                )
            if len(iwu_bdg.index) > 1:
                raise ValueError("Internal Error: To many building data to unpack")

            iwu_idx = iwu_bdg.index[0]

            iwu_bdg = iwu_bdg.loc[iwu_idx, :].to_dict()

            a_ref = iwu_bdg["A_C_Ref"]
            cfg["n_apartments"] = iwu_bdg["n_Apartment"]
        else:
            warnings.warn(
                'No suffucient sufficient keyword arguments provided for the shape. Shape of IWU building "DE.N.SFH.08.Gen.ReEx.001.001" chosen.'
            )
            iwu_idx = "DE.N.SFH.08.Gen.ReEx.001.001"
            iwu_bdg = self.iwu_bdg.loc[iwu_idx, :]
            a_ref = iwu_bdg["A_C_Ref"]
            cfg["n_apartments"] = iwu_bdg["n_Apartment"]

        # get shape values
        cfg = get_shape(cfg, iwu_bdg, a_ref)

        self.IDentries["Shape"] = iwu_idx
        self.IDentries["A_ref"] = cfg["A_ref"]

        # integrate roof tilt
        if "roofTilt" in kwgs:
            cfg["roofTilt"] = kwgs["roofTilt"]
        else:
            if iwu_bdg["Code_RoofType"] in ["FR"]:
                cfg["roofTilt"] = 0.0
            else:
                cfg["roofTilt"] = 45.0
        self.IDentries["roofTilt"] = cfg["roofTilt"]

        # integrate roof orientation
        cfg["roofOrientation"] = kwgs["roofOrientation"]
        self.IDentries["roofOrientation"] = cfg["roofOrientation"]

        return cfg

    def _get_fabric(self, cfg, kwgs):
        if "ID" in kwgs:
            self.IDentries["Fabric"] = kwgs["ID"]
            cfg = get_fabric(cfg, self.iwu_bdg.xs(kwgs["ID"]).to_dict())
            cfg["buildingYear"] = self.iwu_bdg.xs(kwgs["ID"]).to_dict()[
                "Year2_Building"
            ]
        else:
            # get the buildingyear
            year = kwgs["buildingYear"]
            if kwgs["refurbished"]:
                year_before = copy.deepcopy(year)
                year = min(max(year + 40, 1995), 2020)
                warnings.warn(
                    '"refurbished" just overwrites the buildingyear from '
                    + str(year_before)
                    + " to "
                    + str(year)
                )
            elif kwgs["buildnew"]:
                year = 2020
            elif "buildingYear" in kwgs:
                year = kwgs["buildingYear"]
            else:
                raise ValueError('"buildingYear" is required as argument')

            cfg["buildingYear"] = year

            # get all buildings with this year
            iwu_year = self.iwu_bdg[
                (self.iwu_bdg["Year1_Building"] <= year)
                & (year <= self.iwu_bdg["Year2_Building"])
            ]

            # get the one with the most similar reference area
            diff_area = abs(
                iwu_year["A_C_Ref"] * iwu_year["n_Apartment"]
                - cfg["A_ref"] * cfg["n_apartments"]
            )
            iwu_idx = diff_area.idxmin()
            iwu_bdg = iwu_year.xs(iwu_idx).to_dict()

            cfg = get_fabric(cfg, iwu_bdg)

            # set chjosen buildingType as fabric entry
            self.IDentries["Fabric"] = iwu_idx

        # define thermal class
        cfg["thermalClass"] = kwgs["thermalClass"]
        self.IDentries["thermalClass"] = cfg["thermalClass"]

        # if refurbishment is an option for the optimization
        cfg["refurbishment"] = kwgs["refurbishment"]
        self.IDentries["refurbishment"] = cfg["refurbishment"]

        # if refurbishment is an option for the optimization
        cfg["force_refurbishment"] = kwgs["force_refurbishment"]
        if cfg["force_refurbishment"] and not cfg["refurbishment"]:
            raise ValueError(
                'If "force_refurbishment" is activated, "refurbishment" must be activated as well.'
            )
        # TODO add force_refurbishment to ID entries
        # self.IDentries['force_refurbishment'] = cfg['force_refurbishment']

        return cfg

    def _get_equipment(self, cfg, kwgs):
        """
        Gives the configuration for existing energy supply technologies
        in the building.
        """
        # if the hot water is supplied by an electricity boiler or by the
        # heating system
        cfg["hotWaterElec"] = kwgs["hotWaterElec"]
        self.IDentries["hotWaterElec"] = cfg["hotWaterElec"]

        # if hot water is generated electrically, correct the hot water demand
        if not self.ignore_profiles:
            if cfg["hotWaterElec"]:
                cfg["hotWaterLoad"] = cfg["hotWaterLoad"] * 0.6

        # get existing heat supply
        cfg["existingHeatSupply"] = kwgs["existingHeatSupply"]
        self.IDentries["existingHeatSupply"] = cfg["existingHeatSupply"]

        # TODO: replace heat supply with heat equipment age
        cfg["replaceHeatSupply"] = kwgs["replaceHeatSupply"]
        self.IDentries["replaceHeatSupply"] = cfg["replaceHeatSupply"]

        # define if it has already solar thermal
        if "hasSolarThermal" in kwgs:
            cfg["hasSolarThermal"] = kwgs["hasSolarThermal"]
        else:
            # define solar thermal for all post enev 2009 gas boiler buildins
            if cfg["existingHeatSupply"] == "Gas boiler" and (
                cfg["buildingYear"] >= 2009 or kwgs["refurbished"]
            ):
                cfg["hasSolarThermal"] = True

                # TODO: Not used at the moment
                cfg["solarThermalSize"] = 10.0 * cfg["n_apartments"]
            else:
                cfg["hasSolarThermal"] = False
        self.IDentries["hasSolarThermal"] = cfg["hasSolarThermal"]

        # define if it has already photovoltaic
        cfg["hasPhotovoltaic"] = kwgs["hasPhotovoltaic"]
        self.IDentries["hasPhotovoltaic"] = cfg["hasPhotovoltaic"]

        # determine the design supply temperature depending on the size of the
        # building and the age
        if "T_sup" in kwgs:
            T_sup = kwgs["T_sup"]
        else:
            # TODO: find data for this
            T_sup = 70
            if cfg["n_apartments"] > 6:
                T_sup += 5
            if cfg["buildingYear"] > 1990:
                T_sup -= 10
            if cfg["buildingYear"] > 2000:
                T_sup -= 10
            if cfg["buildingYear"] > 2010:
                T_sup -= 10
            if "floorHeating" in kwgs:
                if kwgs["floorHeating"]:
                    T_sup = 40.0
        cfg["T_sup"] = T_sup
        # TODO configure return temperature
        cfg["T_ret"] = 25.0
        self.IDentries["T_sup"] = cfg["T_sup"]

        return cfg

    def _get_finance(self, cfg, kwgs):
        """
        Get the interest rate and the ownership structure of the building
        """
        cfg["ownership"] = kwgs["ownership"]

        cfg["onlyEnergyInvest"] = kwgs["onlyEnergyInvest"]

        if "WACC" in kwgs:
            cfg["WACC"] = kwgs["WACC"]
        else:
            if cfg["ownership"]:
                cfg["WACC"] = 0.03
            else:
                cfg["WACC"] = 0.06

        self.IDentries["WACC"] = cfg["WACC"]
        self.IDentries["ownership"] = cfg["ownership"]
        return cfg


def get_fabric(bdg, iwu_bdg):
    # merge two window types to one window type
    bdg["U_Window"] = (
        iwu_bdg["A_Window_1"] * iwu_bdg["U_Window_1"]
        + iwu_bdg["A_Window_2"] * iwu_bdg["U_Window_2"]
    ) / bdg["A_Window"]
    bdg["g_gl_n_Window"] = (
        iwu_bdg["A_Window_1"] * iwu_bdg["g_gl_n_Window_1"]
        + iwu_bdg["A_Window_2"] * iwu_bdg["g_gl_n_Window_1"]
    ) / bdg["A_Window"]

    # TODO: what means actual? I think after attic and basement condition...
    # get u values of the walls etc.
    for wall in ["Wall_1", "Wall_2", "Wall_3"]:
        bdg["U_" + wall] = iwu_bdg["U_Actual_" + wall]
        bdg["b_Transmission_" + wall] = iwu_bdg["b_Transmission_" + wall]
    for roof in ["Roof_1", "Roof_2"]:
        bdg["U_" + roof] = iwu_bdg["U_Actual_" + roof]
        bdg["b_Transmission_" + roof] = iwu_bdg["b_Transmission_" + roof]
    for door in ["Door_1"]:
        bdg["U_" + door] = iwu_bdg["U_Actual_" + door]
    for floor in ["Floor_1", "Floor_2"]:
        bdg["U_" + floor] = iwu_bdg["U_Actual_" + floor]
        bdg["b_Transmission_" + floor] = iwu_bdg["b_Transmission_" + floor]

    # TODO: make them as own argument and move them to operation
    bdg["n_air_infiltration"] = iwu_bdg["n_air_infiltration"]
    bdg["n_air_use"] = iwu_bdg["n_air_use"]

    return bdg


def get_shape(bdg, iwu_bdg, a_ref):
    """
    Takes the IWU reference building and scales its shape such
     that it fits the given reference area

    :param bdg: Dictionary with the relevant parameters
    :param iwu_bdg: IWU-Reference building as dictionary
    :param a_ref: float
    :return: bdg
    """
    # get new reference area
    bdg["A_ref"] = a_ref

    # get ratio
    ratio = a_ref / iwu_bdg["A_C_Ref"]

    # keep the number of storeys and the height of the room
    bdg["n_Storey"] = iwu_bdg["n_Storey"]
    bdg["h_room"] = iwu_bdg["h_room"]

    # get specific and agreagted windows area
    for di in ["North", "East", "South", "West"]:
        bdg["A_Window_" + di] = iwu_bdg["A_Window_" + di] * (ratio ** 0.5)
    bdg["A_Window_Horizontal"] = (
        iwu_bdg["A_Window_Horizontal"] * ratio / iwu_bdg["n_Storey"]
    )
    bdg["A_Window"] = sum(
        bdg["A_Window_" + di] for di in ["North", "East", "South", "West", "Horizontal"]
    )

    # get shading relevance
    bdg["F_sh_vert"] = iwu_bdg["F_sh_vert"]
    bdg["F_sh_hor"] = iwu_bdg["F_sh_hor"]
    bdg["F_f"] = iwu_bdg["F_f"]
    bdg["F_w"] = iwu_bdg["F_w"]

    # get new shape of wall, roof and floor
    for wall in ["Wall_1", "Wall_2", "Wall_3"]:
        bdg["A_" + wall] = iwu_bdg["A_" + wall] * (ratio ** 0.5)
    for roof in ["Roof_1", "Roof_2"]:
        bdg["A_" + roof] = iwu_bdg["A_" + roof] * (
            1 + (ratio - 1) / iwu_bdg["n_Storey"]
        )
    for floor in ["Floor_1", "Floor_2"]:
        bdg["A_" + floor] = iwu_bdg["A_" + floor] * (
            1 + (ratio - 1) / iwu_bdg["n_Storey"]
        )
    for door in ["Door_1"]:
        bdg["A_" + door] = iwu_bdg["A_" + door] * (ratio ** 0.5)
    return bdg


def get_household_profiles(
    n_persons,
    weather_data,
    weatherID,
    seeds=[0],
    ignore_weather=True,
    mean_load=True,
    cores=mp.cpu_count() - 1,
):
    """
    Gets or creates the relevant occupancy profiles for a building
    simulation or optimization.
    
    
    Parameters
    ----------
    n_persons: integer, required
        Number of persons living in a single appartment.
    weather_data: pd.DataFrame(), required
        A time indexed pandas dataframe containing weather data with 
        the GHI as a column.
    weatherID: str, required
        Giving an ID to the weather data to identify the resulting profile.
    seeds: list, optional (default: [0])
        List of integer seeds to create a number of profiles which have
        similar input parameters, but a varying output. Default, no seed is
        chosen. 
    ignore_weather: bool, optional (default: False)
        Since atm only the GHI is required for the electricity load profile,
        the weather plays a minor role and can be ignored by the identificaiton
        of profiles.
    mean_load: bool, optional (default: True)
        Decides if the created load profiles on 1-minute basis shall be 
        downsampled by taking the mean of 60 minutes or the first value in
        every 60 minutes.
    cores: int, optiona(default: mp.cpu_count() - 1)
        Number of cores used for profile generation.
    """

    # get the potential profile names
    filenames = {}
    for seed in seeds:
        profile_ID = "Profile" + "_occ" + str(int(n_persons)) + "_seed" + str(seed)
        if not ignore_weather:
            profile_ID = profile_ID + "_wea" + str(weatherID)

        if mean_load:
            profile_ID = profile_ID + "_mean"

        filenames[seed] = os.path.join(
            DATA_PATH, "results", "occupantprofiles", profile_ID + ".csv"
        )

    # check how many profiles do not exist#
    not_existing_profiles = {}
    for seed in seeds:
        if not os.path.isfile(filenames[seed]):
            not_existing_profiles[seed] = filenames[seed]

    # run in parallel all profiles
    if len(not_existing_profiles) > 1:
        new_profiles = run_district_year(
            int(n_persons),
            2010,
            len(not_existing_profiles),
            weather_data=weather_data,
            get_hot_water=True,
            resample_mean=mean_load,
            cores=cores,
        )
    # if single profile just create one profile and avoid multiprocessing
    elif len(not_existing_profiles) > 0:
        one_profile = one_household_year(
            int(n_persons),
            2010,
            weather_data=weather_data,
            get_hot_water=True,
            resample_mean=mean_load,
        )
        new_profiles = [one_profile]

    # write results to csv files
    for i, seed in enumerate(not_existing_profiles):
        new_profiles[i].to_csv(not_existing_profiles[seed])

    # load all profiles
    profiles = []
    for seed in seeds:
        profiles.append(pd.read_csv(filenames[seed], index_col=0))

    return profiles


def get_ISO12831_weather(longitude, latitude, year=2010, cosmo=False):
    """

    Gets the test reference year location and the design temperatures for
    the heating system based on the ISO12831.
    Parameters
    ----------
    longitude: float
    latitude: float
    year: int, optional (default: 2010)
    cosmo: bool, optional (default: False)
        If the weather data shall be extracted from the cosmo database.
    Returns
    -------
    weather (DataFrame with TRY weather)
    T_min (design temperature for heating),
    weatherID (str with climate zone)
    """

    # read weather zones
    wzones = pd.read_csv(
        os.path.join(DATA_PATH, "weatherdata", "ISO12831", "T_zones_Ger_final.csv"),
        index_col=0,
        encoding="ISO-8859-1",
    )

    # get distance to all reference weather station points
    dist = ((wzones["Lat"] - latitude) ** 2 + (wzones["Lng"] - longitude) ** 2) ** 0.5

    # if distance to next reference position is to high.
    if min(dist) > 5:
        raise NotImplementedError(
            "The weather data is at the moment" + " only implemented for Germany"
        )

    # get the data from the one with the minimal distance
    loc_w = wzones.loc[dist.idxmin(), :]
    design_T_min = loc_w["Min T"]

    # read weather data of related try region
    if not cosmo:
        weatherID = "TRY_" + str(loc_w["Climate Zone"])
        weather, loc = tsm.readTRY(try_num=loc_w["Climate Zone"], year=year)
    else:
        weather, weatherID = tsm.readtCosmoNetCDF4(
            os.path.join(
                os.environ["DATA_SHARE"], "weather", "cosmo", "rea6", "processed"
            ),
            longitude,
            latitude,
            year,
        )

    return weather, design_T_min, weatherID


if __name__ == "__main__":
    ref_results = pd.read_csv(
        "file:///C:/Users/Leander/sciebo/FZJ/01_FullStateEco/buildingstock/results/20171017_NRW_2_noBdgs_5/bdgResults_9.csv",
        index_col=0,
    )
    ref_results = ref_results.rename(
        columns={
            "Age App.": "buildingYear",
            "Code_AttachedNeighbours": "surrounding",
            "n_Apartment": "n_apartments",
        }
    )
    ref_results["buildingYear"] = ref_results["buildingYear"].astype(int)
    ref_results["a_ref_app"] = ref_results["a_ref_app"].astype(float)
    ref_results["ownership"] = ref_results["ownership"].astype(bool)
    ref_results.drop(["app_group", "location"], axis=1, inplace=True)
    kwgs = ref_results.xs("N28").to_dict()

    kwgs["latitude"] = kwgs["latitude"] + 54
    kwgs["longitude"] = kwgs["longitude"] + 8
    kwgs["varyoccupancy"] = 4
    kwgs["n_apartments"] = 3

    bdg = BuildingConfiguration(kwgs)
    cfg = bdg.getBdgCfg()

    #
    # Form
    #     roof_tilt
    #     roof_orientation
    # Equipment
    #     existingAge - dict
    #     T_supply
    #     refurbished
    #
    # Finance
    #     WACC
    #     MaxInvestmentVolume
    #     InsulationWACC
    # thermalClass
    # roofTilt
    # roofOrientation
    # comfortT_lb
    # comfortT_ub
    # ventControl
    # nightReduction
    # capControl
    # costdata
    # elecLoad
    # elecLoadID