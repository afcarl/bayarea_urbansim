from urbansim.developer import sqftproforma
from urbansim.utils import networks
import urbansim.models.yamlmodelrunner as ymr
from dataset import *
import time


def buildings_df(dset, addprices=False, filter=None):
    buildings = dset.view("buildings")
    if addprices:
        flds = buildings.flds + ["residential_sales_price", "residential_rent", "non_residential_rent"]
    else:
        flds = buildings.flds
    bdf = buildings.build_df(flds=flds)
    if filter is not None:
        bdf.query(filter)
    return dset.merge_nodes(bdf.fillna(0))


def households_df(dset):
    return dset.view("households").build_df()


def jobs_df(dset):
    return dset.view("jobs").build_df()


def homesales_df(dset):
    return dset.merge_nodes(dset.view("homesales").build_df())


def apartments_df(dset):
    return dset.merge_nodes(dset.view("apartments").build_df())


def costar_df(dset):
    return dset.merge_nodes(dset.view("costar").build_df())


def clear_cache(dset):
    dset.clear_views()


def cache_variables(dset):
    buildings_df(dset)
    households_df(dset)
    jobs_df(dset)
    homesales_df(dset)
    apartments_df(dset)
    costar_df(dset)


# residential sales hedonic
def rsh_estimate(dset):
    return ymr.hedonic_estimate(homesales_df(dset), "rsh.yaml")


def rsh_simulate(dset):
    return ymr.hedonic_simulate(buildings_df(dset), "rsh.yaml",
                                dset.buildings, "residential_sales_price")


# residential rent hedonic
def rrh_estimate(dset):
    return ymr.hedonic_estimate(apartments_df(dset), "rrh.yaml")


def rrh_simulate(dset):
    return ymr.hedonic_simulate(buildings_df(dset), "rrh.yaml",
                                dset.buildings, "residential_rent")


# non-residential hedonic
def nrh_estimate(dset):
    return ymr.hedonic_estimate(costar_df(dset), "nrh.yaml")


def nrh_simulate(dset):
    return ymr.hedonic_simulate(buildings_df(dset), "nrh.yaml",
                                dset.buildings, "non_residential_rent")


# household location choice
def _hlcm_estimate(dset, cfgname):
    return ymr.lcm_estimate(households_df(dset),
                            "building_id",
                            buildings_df(dset,
                                         addprices=True,
                                         filter="general_type == 'Residential'"),
                            cfgname)


def _hlcm_simulate(dset, cfgname):
    units = ymr.get_vacant_units(households_df(dset),
                                 "building_id",
                                 buildings_df(dset,
                                              addprices=True,
                                              filter="general_type == 'Residential'"),
                                 "residential_units")
    return ymr.lcm_simulate(households_df(dset), units, cfgname, dset.households, "building_id")


# household location choice owner
def hlcmo_estimate(dset):
    return _hlcm_estimate(dset, "hlcmo.yaml")


def hlcmo_simulate(dset):
    return _hlcm_simulate(dset, "hlcmo.yaml")


# household location choice renter
def hlcmr_estimate(dset):
    return _hlcm_estimate(dset, "hlcmr.yaml")


def hlcmr_simulate(dset):
    return _hlcm_simulate(dset, "hlcmr.yaml")


# employment location choice
def elcm_estimate(dset):
    return ymr.lcm_estimate(jobs_df(dset),
                            "building_id",
                            buildings_df(dset,
                                         addprices=True,
                                         filter="general_type != 'Residential'"),
                            "elcm.yaml")


def elcm_simulate(dset):
    units = ymr.get_vacant_units(jobs_df(dset),
                                 "building_id",
                                 buildings_df(dset,
                                              addprices=True,
                                              filter="general_type != 'Residential'"),
                                 "non_residential_units")
    return ymr.lcm_simulate(jobs_df(dset), units, "elcm.yaml", dset.jobs, "building_id")


def households_relocation(dset):
    return ymr.simple_relocation(dset.households, .05)


def jobs_relocation(dset):
    return ymr.simple_relocation(dset.jobs, .08)


def households_transition(dset):
    return ymr.simple_transition(dset, "households", .05)


def jobs_transition(dset):
    return ymr.simple_transition(dset, "jobs", .05)


def build_networks():
    if not networks.NETWORKS:
        networks.NETWORKS = networks.Networks(
            [os.path.join(misc.data_dir(), x) for x in ['osm_bayarea.jar']],
            factors=[1.0],
            maxdistances=[2000],
            twoway=[1],
            impedances=None)


def neighborhood_vars(dset):
    nodes = networks.from_yaml(dset, "networks.yaml")
    dset.save_tmptbl("nodes", nodes)


def price_vars(dset):
    nodes = networks.from_yaml(dset, "networks2.yaml")
    dset.save_tmptbl("nodes_prices", nodes)


def feasibility(dset):
    dev = sqftproforma.SqFtProForma()

    parcels = Parcels(dset)
    df = parcels.build_df()

    # add prices for each use
    for use in dev.config.uses:
        df[use] = parcels.price(use)

    # convert from cost to yearly rent
    df["residential"] *= dev.config.cap_rate

    d = {}
    for form in dev.config.forms:
        print "Computing feasibility for form %s" % form
        d[form] = dev.lookup(form, df[parcels.allowed(form)])

    far_predictions = pd.concat(d.values(), keys=d.keys(), axis=1)

    dset.save_tmptbl("feasibility", far_predictions)


def developer(dset):
    type_d = {
        'residential': [1, 2, 3],
        'industrial': [7, 8, 9],
        'retail': [10, 11],
        'office': [4],
        'mixedresidential': [12],
        'mixedoffice': [14],
    }
    pass


def _run_models(dset, model_list, years):

    for year in years:

        dset.year = year

        t1 = time.time()

        for model in model_list:
            t2 = time.time()
            print "\n" + model + "\n"
            globals()[model](dset)
            print "Model %s executed in %.3fs" % (model, time.time()-t2)
        print "Year %d completed in %.3fs" % (year, time.time()-t1)