#!/usr/bin/env python
import pandas as pd
import numpy as np
import json

MAX_CONTEST_CODE = '0062'
CONTEST_COLS = ['Contest name', '# Completed precincts',
                '# of Eligible Precincts', 'Total votes']
CAND_COLS = ['Candidate Name', 'Votes', '% of Votes']

# disable pandas 'chained assignment' warning
pd.options.mode.chained_assignment = None


def main():
    '''
    Transforms CBOE election results into Chi.vote style JSON results 
    '''

    # get layout dataframe
    LAYOUT_PATH = './layout.txt'
    layout_df = create_layout_df(LAYOUT_PATH)

    # get results dataframe
    RESULTS_PATH = './results.txt'
    results_df = create_results_df(RESULTS_PATH, layout_df)

    # filter results down to candidate races only
    mask = results_df['Contest Code'] <= MAX_CONTEST_CODE
    results_df = results_df[mask]

    # transform results into Chi.vote format
    #
    # - NOTE: returned dict includes numpy objects. don't worry about this --
    #         we take of these in a custom json encoder (MyEncoder).
    #
    # - NOTE: this uses global vars CONTEST_COLS and CAND_COLS
    results_dict = create_transformed_results_dict(results_df)

    # write results dict to json
    JSON_PATH = './results.json'
    with open(JSON_PATH, 'w') as outfile:
        json.dump(results_dict, outfile, cls=MyEncoder)

    # write results dict again to timestamped filepath
    # TODO: we should write to both files without also processing it twice
    timestamp = results_dict['timestamp']
    timestamped_path = f'{JSON_PATH[:-5]}.{timestamp}.json'
    with open(timestamped_path, 'w') as outfile:
        json.dump(results_dict, outfile, cls=MyEncoder)


def create_layout_df(filepath):
    '''
    Generates layout dataframe, with which we interpret results file
    '''
    layout_df = pd.read_csv(filepath, sep='\t+', engine='python')

    # generate colspecs tuples, per https://pandas.pydata.org/pandas-docs/version/0.22/generated/pandas.read_fwf.html
    layout_df['colspecs'] = layout_df['Column Position'].apply(
        lambda x: (int(x.split('-')[0]) - 1, int(x.split('-')[1]))
    )

    return layout_df


def create_results_df(filepath_or_buffer, layout_df):
    '''
    Generates results dataframe using pandas.read_fwf

    See documentation for accepted values for filepath_or_buffer

    Docs: https://pandas.pydata.org/pandas-docs/version/0.22/generated/pandas.read_fwf.html
    '''
    results_df = pd.read_fwf(filepath_or_buffer,
                             colspecs=layout_df['colspecs'].values.tolist(),
                             names=layout_df['Summary Export File Format'].values.tolist(
                             ),
                             converters={
                                 'Contest Code': str,
                                 'Candidate Number': str,
                                 '# Completed precincts': int,
                                 '# of Eligible Precincts': int,
                                 'Votes': int
                             }
                             )

    return results_df


def _calc_percent(val, total):
    '''
    Helper function to get pct of total votes as a string.
    '''
    if (total > 0):
        return "%.1f%%" % (val/total * 100)
    else:
        return "N/A"


def build_contests(df):
    '''
    Generates a dict of values keyed to 'Contest Code', based on CONTEST_COLS and CAND_COLS.

    example output:
    {
        "0010": {
            "meta": ["Mayor", 1, 1000, 100],
            "cands": [
                ["Rahm Emanuel", 6060, "60.5%"],
                ["Dorothy Brown", 3034, "30.3%"]
            ]
        },
        "0011": {
            "meta": ["Clerk", 1, 1000, 100],
            "cands": [
            ["Anna Valencia", 100, "100%"]
            ]
        }
    }
    '''

    contests = {}

    for key, contest in df.groupby('Contest Code'):
        # for now, only columns that already exist in the results
        meta = contest.iloc[0][np.intersect1d(
            contest.columns.values, CONTEST_COLS)]
        cands = contest[np.intersect1d(contest.columns.values, CAND_COLS)]

        # calculate pct values
        if ('Votes' in CAND_COLS
                    and ('Total votes' in CONTEST_COLS
                         or '% of Votes' in CAND_COLS)
                ):
            total_votes = cands['Votes'].sum()
            meta['Total votes'] = total_votes
            cands['% of Votes'] = cands['Votes'].apply(
                _calc_percent, total=total_votes)

        contests[key] = {
            'meta': meta[CONTEST_COLS].values,
            'cands': cands[CAND_COLS].values
        }

    return contests


def get_local_datetime():
    '''
    Generates Python datetime object in local timezone
    '''
    from datetime import datetime
    from tzlocal import get_localzone

    tz = get_localzone()  # local timezone
    d = datetime.now(tz)  # or some other local date

    return d


def create_transformed_results_dict(results_df):
    '''
    Generates final dict of all the data we want to pass along.
    '''
    d = get_local_datetime()

    results = {
        "contest_headers": CONTEST_COLS,
        "cand_headers": CAND_COLS,
        "datetime": d.replace(microsecond=0).isoformat(),
        'timestamp': int(d.replace(microsecond=0).timestamp()),
        "contests": build_contests(results_df)
    }

    return results


class MyEncoder(json.JSONEncoder):
    """
    We have to use a custom encoder because pandas uses special numpy 
    object types that json doesn't like.

    Source: https://stackoverflow.com/a/27050186
    """

    def default(self, obj):
        import numpy as np

        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(MyEncoder, self).default(obj)


if __name__ == '__main__':
    main()
